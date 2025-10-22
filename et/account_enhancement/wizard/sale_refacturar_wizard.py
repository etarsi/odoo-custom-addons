# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math
from datetime import timedelta

class SaleRefacturarWizard(models.TransientModel):
    _name = 'sale.refacturar.wizard'
    _description = 'Wizard: Refacturar Facturación desde Pedido de Venta'

    sale_id = fields.Many2one('sale.order', string='Pedido de venta', required=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True)
    condicion_m2m_id = fields.Many2one('condicion.venta', string='Condición de Venta', required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de precios', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        sale = self.env['sale.order'].browse(active_id)
        if not sale or sale._name != 'sale.order':
            raise UserError(_('Este asistente debe abrirse desde un pedido de venta.'))

        res.update({
            'sale_id': sale.id,
            'partner_id': sale.partner_id.id,
        })
        return res

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            domain = []
            self.condicion_m2m_id = False
            if self.company_id.id == 1:  # Producción B
                domain = [('name', '=', 'TIPO 3')]
                return {'domain': {'condicion_m2m_id': domain}}
            else:
                return {'domain': {'condicion_m2m_id': [('name', '!=', 'TIPO 3')]}}

    def set_due_date_plus_x(self, x):
        today = fields.Date.context_today(self)
        new_date = today + timedelta(days=x)
        return new_date

    def _prepare_invoice_base_vals(self, company):
        invoice_date_due = fields.Date.context_today(self)

        if self.sale_id.payment_term_id:
            extra_days = max(self.sale_id.payment_term_id.line_ids.mapped('days') or [0])
            invoice_date_due = self.set_due_date_plus_x(extra_days)
        
        return {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'partner_shipping_id': self.sale_id.partner_shipping_id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': invoice_date_due,
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'invoice_origin': self.sale_id.name,
            'payment_reference': self.sale_id.name,
            'fiscal_position_id': self.sale_id.partner_invoice_id.property_account_position_id.id,
            'invoice_payment_term_id': self.sale_id.payment_term_id,
            'wms_code': False,
        }

    def action_create_invoice_from_sale(self):
        self.ensure_one()

        sale = self.sale_id
        if not sale:
            raise UserError(_("Este asistente debe abrirse desde un pedido de venta."))

        # TIPO (tomá el que uses en tu wizard)
        tipo = (self.condicion_m2m_id.name or '').upper().strip()  # o (self.x_order_type.name or '')
        proportion_blanco, proportion_negro = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }.get(tipo, (1.0, 0.0))

        company_blanca = self.company_id or sale.company_id
        # Reemplazá browse(1) por un campo en el wizard si querés parametrizarlo
        company_negra = self.env['res.company'].browse(1) if proportion_negro > 0 else False

        invoice_lines_blanco = []
        invoice_lines_negro = []
        sequence = 1

        # Construimos desde LÍNEAS DE VENTA (no inventario)
        for so_line in sale.order_line.filtered(lambda l: not l.display_type and l.product_id):
            # Elegí tu política de cantidad:
            qty_total = so_line.qty_to_invoice or so_line.qty_delivered or so_line.product_uom_qty
            if qty_total <= 0:
                continue

            # Base: usamos el preparador de la línea para factura
            base_vals = so_line._prepare_invoice_line(sequence=sequence)
            # Aseguramos cantidad y precio base según la línea
            base_vals['quantity'] = qty_total
            base_vals['price_unit'] = so_line.price_unit
            base_vals['discount'] = so_line.discount
            # tax_ids ya viene de la línea

            # Proporciones
            qty_blanco = math.floor(qty_total * proportion_blanco)
            qty_negro = qty_total - qty_blanco

            if proportion_blanco > 0 and qty_blanco:
                blanco_vals = base_vals.copy()
                blanco_vals['quantity'] = qty_blanco
                # impuestos de la línea (respetando FP del pedido al validar la factura)
                invoice_lines_blanco.append((0, 0, blanco_vals))

            if proportion_negro > 0 and qty_negro:
                negro_vals = base_vals.copy()
                negro_vals['quantity'] = qty_negro
                # sin impuestos en NEGRA
                negro_vals['tax_ids'] = False
                # multiplicador precio (salvo TIPO 3)
                if tipo == 'TIPO 3':
                    negro_vals['price_unit'] = so_line.price_unit
                else:
                    negro_vals['price_unit'] = so_line.price_unit * 1.21
                invoice_lines_negro.append((0, 0, negro_vals))

            sequence += 1

        invoices = self.env['account.move']

        # ---- Crear factura BLANCA ----
        if invoice_lines_blanco:
            vals_blanco = self._prepare_invoice_base_vals(company_blanca)
            vals_blanco.update({
                'invoice_line_ids': invoice_lines_blanco,
                'invoice_user_id': sale.user_id.id,
                'partner_bank_id': False,
                'company_id': company_blanca.id,
            })
            if not vals_blanco.get('journal_id'):
                journal = self.env['account.journal'].search([
                    ('type', '=', 'sale'),
                    ('company_id', '=', company_blanca.id)
                ], limit=1)
                if not journal:
                    raise UserError(_("No se encontró un diario de ventas para la compañía %s.") % (company_blanca.name,))
                vals_blanco['journal_id'] = journal.id

            invoices |= self.env['account.move'].with_company(company_blanca).create(vals_blanco)

        # ---- Crear factura NEGRA ----
        if invoice_lines_negro and company_negra:
            vals_negro = self._prepare_invoice_base_vals(company_negra)
            vals_negro.update({
                'invoice_line_ids': invoice_lines_negro,
                'invoice_user_id': sale.user_id.id,
                'partner_bank_id': False,
                'company_id': company_negra.id,
            })
            journal = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', company_negra.id)
            ], limit=1)
            if not journal:
                raise UserError(_("No se encontró un diario de ventas para la compañía (Negra)."))
            vals_negro['journal_id'] = journal.id

            invoices |= self.env['account.move'].with_company(company_negra).create(vals_negro)

        # Origen de la factura = Pedido
        invoices.write({'invoice_origin': sale.name})

        # Abrir resultado
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        if len(invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoices.id
        else:
            action['domain'] = [('id', 'in', invoices.ids)]
        return action


        if not inv_lines_blanca and not inv_lines_negra:
            raise UserError(_('No hay líneas para refacturar.'))

        moves = self.env['account.move']

        # Crear Factura BLANCA
        if inv_lines_blanca:
            j_blanca = _find_sale_journal(company_blanca)
            vals_b = {
                'move_type': 'out_invoice',
                'company_id': company_blanca.id,
                'journal_id': j_blanca.id,
                'partner_id': sale.partner_invoice_id.id or sale.partner_id.id,
                'partner_shipping_id': sale.partner_shipping_id.id or sale.partner_id.id,
                'invoice_origin': sale.name,
                'invoice_user_id': sale.user_id.id,
                'invoice_payment_term_id': sale.payment_term_id.id,
                'fiscal_position_id': fpos_blanca.id if fpos_blanca else False,
                'currency_id': company_blanca.currency_id.id,
                'invoice_line_ids': inv_lines_blanca,
            }
            move_b = self.env['account.move'].with_company(company_blanca).create(vals_b)
            moves |= move_b

        # Crear Factura NEGRA
        if inv_lines_negra:
            j_negra = _find_sale_journal(company_negra)
            vals_n = {
                'move_type': 'out_invoice',
                'company_id': company_negra.id,
                'journal_id': j_negra.id,
                'partner_id': sale.partner_invoice_id.id or sale.partner_id.id,
                'partner_shipping_id': sale.partner_shipping_id.id or sale.partner_id.id,
                'invoice_origin': sale.name,
                'invoice_user_id': sale.user_id.id,
                'invoice_payment_term_id': sale.payment_term_id.id,
                'currency_id': company_negra.currency_id.id,
                'invoice_line_ids': inv_lines_negra,
            }
            move_n = self.env['account.move'].with_company(company_negra).create(vals_n)
            moves |= move_n

        # Abrir resultado
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        if len(moves) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = moves.id
        else:
            action['domain'] = [('id', 'in', moves.ids)]
        return action