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

    # ---------- helper: precio por lista compatible v15 ----------
    def _pl_price(self, product, qty, uom, partner, date_order=None):
        """Devuelve el precio según la lista elegida (o None si no hay lista)."""
        if not self.pricelist_id:
            return None
        ctx = dict(self.env.context or {})
        if uom:
            ctx['uom'] = uom.id
        if date_order:
            ctx['date'] = fields.Date.to_date(date_order)
        pl = self.pricelist_id.with_context(ctx)
        # v15 CE
        if hasattr(pl, 'get_product_price'):
            return pl.get_product_price(product, qty, partner)
        # Fallback conocido
        if hasattr(pl, 'get_product_price_rule'):
            price, _rule = pl.get_product_price_rule(product, qty, partner)
            return price
        return None

    def action_create_invoice_from_sale(self):
        """Crea factura(s) a partir de las LÍNEAS DEL PEDIDO (no del picking)."""
        self.ensure_one()
        sale = self.sale_id
        if not sale:
            raise UserError(_("Este asistente debe abrirse desde un pedido de venta."))

        # Proporciones por TIPO
        tipo = (self.condicion_m2m_id.name or '').upper().strip()
        prop_blanco, prop_negro = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }.get(tipo, (1.0, 0.0))

        # Compañías
        company_blanca = self.company_id or sale.company_id
        # Reemplazá este browse(1) por un campo en el wizard: self.company_negra_id
        company_negra = self.env['res.company'].browse(1) if prop_negro > 0 else False
        # company_negra = self.company_negra_id if prop_negro > 0 else False
        if prop_negro > 0 and not company_negra:
            raise UserError(_("Debes seleccionar la Compañía (Negra) para este esquema."))

        # Diarios
        def _find_sale_journal(company):
            j = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
            if not j:
                raise UserError(_('No hay diario de ventas para la compañía %s.') % company.display_name)
            return j

        # Posición fiscal (Blanca)
        fpos_blanca = sale.partner_invoice_id.property_account_position_id.with_company(company_blanca) if sale.partner_invoice_id else False

        # Construir líneas desde SALE ORDER LINES (las “mismas que en la factura” según TIPO)
        inv_lines_blanca, inv_lines_negra = [], []

        for so_line in sale.order_line.filtered(lambda l: not l.display_type and l.product_id):
            # Cantidad base a facturar (elegí la que necesites: qty_to_invoice / qty_delivered / product_uom_qty)
            qty_total = so_line.qty_to_invoice or so_line.qty_delivered or so_line.product_uom_qty
            if qty_total <= 0:
                continue

            uom = so_line.product_uom
            rounding = uom.rounding or 0.01

            # Proporciones con redondeo de UdM
            qty_blanca = round(qty_total * prop_blanco / rounding) * rounding
            qty_negra  = max(qty_total - qty_blanca, 0.0)

            # Precio base (usa lista del wizard si se eligió; si no, toma el del pedido)
            price_unit = so_line.price_unit
            pl = self._pl_price(so_line.product_id, qty_total, uom, sale.partner_id, sale.date_order)
            if pl is not None:
                price_unit = pl

            discount = so_line.discount  # copiamos descuento del pedido
            taxes = so_line.tax_id

            # -------- BLANCA --------
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

            # -------- NEGRA --------
            if company_negra and qty_negra > 0:
                # sin impuestos; multiplicador 1.21 salvo TIPO 3
                price_negra = price_unit * (1.0 if tipo == 'TIPO 3' else 1.21)
                account_negra = so_line.product_id.get_product_income_account(return_default=True)

                inv_lines_negra.append((0, 0, {
                    'product_id': so_line.product_id.id,
                    'name': so_line.name or so_line.product_id.display_name,
                    'quantity': qty_negra,
                    'product_uom_id': uom.id,
                    'price_unit': price_negra,
                    'discount': discount,
                    'tax_ids': [(6, 0, [])],  # explícitamente sin impuestos
                    'account_id': account_negra.id if account_negra else False,
                    'sale_line_ids': [(6, 0, [so_line.id])],
                }))

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