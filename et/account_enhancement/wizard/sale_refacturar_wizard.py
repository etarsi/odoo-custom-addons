# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math

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

    def action_confirm(self):
        self.ensure_one()
        sale = self.sale_id
        if not sale:
            raise UserError(_("Este asistente debe abrirse desde un pedido de venta."))

        # Proporciones por tipo (desde condicion_m2m_id.name)
        tipo = (self.condicion_m2m_id.name or '').upper().strip()
        prop_blanco, prop_negro = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }.get(tipo, (1.0, 0.0))

        if prop_negro > 0.0 and not self.company_id:
            # si vas a emitir la "negra" con otra compañía, agregá un campo company_negra_id y usalo aquí
            company_negra = self.env['res.company'].browse(1)  # TODO: reemplazar por un campo en el wizard
        else:
            company_negra = False

        company_blanca = self.company_id or sale.company_id

        # diarios
        def _find_sale_journal(company):
            j = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
            if not j:
                raise UserError(_('No hay diario de ventas para la compañía %s.') % company.display_name)
            return j

        # posición fiscal para blanca
        fpos_blanca = sale.partner_invoice_id.property_account_position_id.with_company(company_blanca) if sale.partner_invoice_id else False

        # construir líneas desde SALE ORDER LINES (no picking)
        inv_lines_blanca, inv_lines_negra = [], []
        for so_line in sale.order_line.filtered(lambda l: not l.display_type and l.product_id):
            # cantidad base (usá qty_delivered, qty_to_invoice o product_uom_qty según tu caso)
            qty_total = so_line.qty_delivered or so_line.product_uom_qty
            if qty_total <= 0:
                continue

            uom = so_line.product_uom
            rounding = uom.rounding or 0.01

            qty_blanca = round(qty_total * prop_blanco / rounding) * rounding
            qty_negra  = max(qty_total - qty_blanca, 0.0)

            # precio base (lista si se definió)
            price_unit = so_line.price_unit
            pl = self._pl_price(so_line.product_id, qty_total, uom, sale.partner_id)
            if pl is not None:
                price_unit = pl

            discount = so_line.discount  # copiamos descuento del pedido
            taxes = so_line.tax_id

            # --- BLANCA ---
            if qty_blanca > 0:
                taxes_blanca = taxes
                if fpos_blanca:
                    taxes_blanca = fpos_blanca.map_tax(taxes, so_line.product_id, sale.partner_invoice_id)
                account_blanca = so_line.product_id.with_company(company_blanca).get_product_income_account(return_default=True)
                if fpos_blanca:
                    account_blanca = fpos_blanca.map_account(account_blanca)

                inv_lines_blanca.append((0, 0, {
                    'product_id': so_line.product_id.id,
                    'name': so_line.name or so_line.product_id.display_name,
                    'quantity': qty_blanca,
                    'product_uom_id': uom.id,
                    'price_unit': price_unit,
                    'discount': discount,
                    'tax_ids': [(6, 0, taxes_blanca.ids)],
                    'account_id': account_blanca.id if account_blanca else False,
                    'sale_line_ids': [(6, 0, [so_line.id])],
                }))

            # --- NEGRA ---
            if company_negra and qty_negra > 0:
                price_negra = price_unit * (1.0 if tipo == 'TIPO 3' else 1.21)
                account_negra = so_line.product_id.get_product_income_account(return_default=True)

                inv_lines_negra.append((0, 0, {
                    'product_id': so_line.product_id.id,
                    'name': so_line.name or so_line.product_id.display_name,
                    'quantity': qty_negra,
                    'product_uom_id': uom.id,
                    'price_unit': price_negra,
                    'discount': discount,
                    'tax_ids': [(6, 0, [])],  # sin impuestos
                    'account_id': account_negra.id if account_negra else False,
                    'sale_line_ids': [(6, 0, [so_line.id])],
                }))

        if not inv_lines_blanca and not inv_lines_negra:
            raise UserError(_('No hay líneas para refacturar.'))

        moves = self.env['account.move']

        # crear BLANCA
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

        # crear NEGRA
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

        # abrir resultado
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        if len(moves) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = moves.id
        else:
            action['domain'] = [('id', 'in', moves.ids)]
        return action
    
    def _prepare_invoice_base_vals(self, company):
        partner = self.partner_id
        invoice_date_due = fields.Date.context_today(self)

        if self.sale_id.payment_term_id:
            extra_days = max(self.sale_id.payment_term_id.line_ids.mapped('days') or [0])
            invoice_date_due = self.set_due_date_plus_x(extra_days)
        
        return {
            'move_type': 'out_invoice',
            'partner_id': self.sale_id.partner_invoice_id,
            'partner_shipping_id': self.sale_id.partner_shipping_id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': invoice_date_due,
            'company_id': self.sale_id.company_id.id,
            'currency_id': self.sale_id.company_id.currency_id.id,
            'invoice_origin': self.origin or self.name,
            'payment_reference': self.name,
            'fiscal_position_id': self.sale_id.partner_invoice_id.property_account_position_id.id,
            'invoice_payment_term_id': self.sale_id.payment_term_id,
            'wms_code': self.codigo_wms,
        }