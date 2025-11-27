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
            domain2 = []
            self.condicion_m2m_id = False
            self.pricelist_id = False
            if self.company_id.id == 1:  # Producción B
                domain2 = [('list_default_b', '=', True)]
                domain = [('name', '=', 'TIPO 3')]
                self.condicion_m2m_id = self.env['condicion.venta'].search([('name', '=', 'TIPO 3')], limit=1)
                return {'domain': {'condicion_m2m_id': domain, 'pricelist_id': domain2}}
            else:
                self.condicion_m2m_id = self.env['condicion.venta'].search([('name', '=', 'TIPO 1')], limit=1)
                self.pricelist_id = self.env['product.pricelist'].search([('is_default', '=', True)], limit=1)
                return {'domain': {'condicion_m2m_id': [('name', '=', 'TIPO 1')], 'pricelist_id': [('list_default_b', '!=', True)]}}

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
        #self.ensure_one()

        sale = self.sale_id
        if not sale:
            raise UserError(_("Este asistente debe abrirse desde un pedido de venta."))
        
        # no debe dejar refacturar si la venta esta en borrador
        if sale.state not in ['sale', 'done']:
            raise UserError(_("No se puede refacturar un pedido que no está confirmado."))

        # TIPO
        tipo = (self.condicion_m2m_id.name or '').upper().strip()
        proportion_blanco, proportion_negro = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }.get(tipo, (1.0, 0.0))

        company_blanca = self.company_id
        company_negra = self.env['res.company'].browse(1) if proportion_negro > 0 else False

        invoice_lines_blanco = []
        invoice_lines_negro = []
        sequence = 1
        impuestos = False
        for so_line in sale.order_line.filtered(lambda l: not l.display_type and l.product_id and l.is_available):
            #IMPUESTOS QUE TINE LA VENTA 
            if so_line.tax_id:
                impuestos = self._asignacion_tax_invoice(so_line.tax_id)
            # Elegí tu política de cantidad:
            qty_total = so_line.qty_to_invoice or so_line.qty_delivered or so_line.product_uom_qty
            if qty_total <= 0:
                continue

            base_vals = so_line._prepare_invoice_line(sequence=sequence)
            base_vals['quantity'] = qty_total
            base_vals['price_unit'] = so_line.price_unit
            base_vals['discount'] = so_line.discount

            # Proporciones
            qty_blanco = math.floor(qty_total * proportion_blanco)
            qty_negro = qty_total - qty_blanco

            if proportion_blanco > 0 and qty_blanco:
                blanco_vals = base_vals.copy()
                blanco_vals['quantity'] = qty_blanco
                blanco_vals['tax_ids'] = impuestos
                invoice_lines_blanco.append((0, 0, blanco_vals))

            if proportion_negro > 0 and qty_negro:
                negro_vals = base_vals.copy()
                negro_vals['quantity'] = qty_negro
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
            action = {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'views': [(self.env.ref('account.view_move_form').id, 'form')],
                'target': 'current',
                'res_id': invoices.id,
                'context': dict(self.env.context, default_move_type='out_invoice'),
            }
        else:
            action = {
                'type': 'ir.actions.act_window',
                'name': 'Facturas de Cliente',
                'res_model': 'account.move',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', invoices.ids)],
                'target': 'current',
                'context': dict(self.env.context, search_default_customer=1, default_move_type='out_invoice'),
            }
        return action

    def _asignacion_tax_invoice(self, tax_ids):
        tax = self.env['account.tax']
        mapped = tax.browse()
        for tax in tax_ids:
            candidate = tax.search([
                ('company_id', '=', self.company_id.id),
                ('type_tax_use', '=', tax.type_tax_use),
                ('description', '=', tax.description), 
            ], limit=1)
            if candidate:
                mapped |= candidate
        return mapped