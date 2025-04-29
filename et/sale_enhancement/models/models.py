from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    # heredados
    note = fields.Html('Terms and conditions')
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', check_company=True,  # Unrequired company
        required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'sale': [('readonly', False)],},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", tracking=1,
        help="If you change the pricelist, only newly added lines will be affected.")

    special_price = fields.Boolean('Precios especiales')
    order_subtotal = fields.Float('Subtotal', compute='_compute_subtotal', readonly=True)
    global_discount = fields.Float('Descuento', default=0)

    def action_confirm(self):
        res = super().action_confirm()
        for record in self:
            company_letter = record._get_company_letter(record)

            record.name = f"{record.name} - {company_letter}"
        
        return res

    def _get_company_letter(self, order):
        company_id = order.company_id
        l = 'S'

        if company_id.id == 2:
            l = 'S'
        elif company_id.id == 3:
            l = 'B'
        elif company_id.d == 4:
            l = 'F'

        return l


    # Forzar comercial correcto
    def create(self, vals):
        res = super().create(vals)

        comercial_id = res.partner_id.user_id

        if comercial_id:
            res.user_id = comercial_id
        return res
    

    @api.depends('amount_tax', 'amount_untaxed', 'order_line.tax_id')
    def _compute_subtotal(self):
        for record in self:
            if not record.order_line:
                record.order_subtotal = record.amount_untaxed
                continue  
            taxes_found = any(
                tax.id in [62, 185, 309, 433] for line in record.order_line for tax in line.tax_id
            )

            record.order_subtotal = record.amount_untaxed * 1.21 if taxes_found else record.amount_untaxed

    @api.onchange('global_discount')
    def _onchange_discount(self):
        for record in self:
            if record.order_line:
                for line in record.order_line:
                    line.discount = record.global_discount

    def update_prices(self):
        self.ensure_one()
        for line in self._get_update_prices_lines():
            line.product_uom_change()
            line.discount = 0
            line._onchange_discount()
        self.show_update_pricelist = False

    @api.onchange('order_line')
    def _onchange_lines_bultos(self):
        for record in self:
            record.packaging_qty = 0
            for line in record.order_line:
                record.packaging_qty += line.product_packaging_qty


    @api.model
    def _default_note(self):
        return

class SaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'

    def _update_line_quantity(self, values):
        orders = self.mapped('order_id')
        for order in orders:
            order_lines = self.filtered(lambda x: x.order_id == order)
            msg = "<b>" + _("The ordered quantity has been updated.") + "</b><ul>"
            for line in order_lines:
                msg += "<li> %s: <br/>" % line.product_id.display_name
                msg += _(
                    "Ordered Quantity: %(old_qty)s -> %(new_qty)s",
                    old_qty=line.product_uom_qty,
                    new_qty=values["product_uom_qty"]
                ) + "<br/>"
                if line.product_id.type in ('consu', 'product'):
                    msg += _("Delivered Quantity: %s", line.qty_delivered) + "<br/>"
                msg += _("Invoiced Quantity: %s", line.qty_invoiced) + "<br/>"
            msg += "</ul>"
            # order.message_post(body=msg)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for record in self:
            record.discount = record.order_id.global_discount
            packaging_ids = record.product_id.packaging_ids
            if packaging_ids:
                record.write(
                            {
                                'product_packaging_id': packaging_ids[0],
                            })            
            
                        
    ## DESHABILITAR ADVERTENCIA DE UNIDAD X BULTO                    
    @api.onchange('product_packaging_id')
    def _onchange_product_packaging_id(self):
        return    

    @api.onchange('product_uom_qty')
    def _onchange_price_unit(self):
        for record in self:
            so_config = self.env['sale.order.settings'].browse(1)
            if so_config:
                if so_config.carga_unidades and so_config.activo:
                    if record.product_packaging_id:
                        record.product_packaging_qty = record.product_uom_qty / record.product_packaging_id.qty

class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'


    property_delivery_carrier_id = fields.Many2one('delivery.carrier', company_dependent=False, string="Delivery Method", help="Default delivery method used in sales orders.")


class SaleOrderSplitWizardInherit(models.TransientModel):
    _inherit = 'sale.order.split.wizard'

    percentage = fields.Float(
        string='Porcentaje (%)',
        digits=(10, 2),
        required=True,
        default=lambda self: self._default_percentage()
    )


    def _default_percentage(self):
        sale_order_id = self._context.get('active_id')
        sale_order = self.env['sale.order'].browse(sale_order_id)
        if sale_order and sale_order.condicion_m2m_numeric:
            try:
                return float(sale_order.condicion_m2m_numeric)
            except ValueError:
                raise UserError(_("condicion_m2m_numeric field must be a valid number."))

    def action_split_sale_orders(self):

        original_order = self.env['sale.order'].browse(self._context.get('active_id'))

        if original_order.splitted:
            raise UserError(_("La Orden de Venta original ya está dividida."))

        new_orders = self.env['sale.order']

        company_id_1 = original_order.company_id.id
        company_id_2 = int(self.env['ir.config_parameter'].sudo().get_param('sale_order_split.company_id'))
        company_ids = [company_id_1, company_id_2]

        for company_id in company_ids:
            name = self.env['res.company'].sudo().search([('id','=',company_id)]).name
            new_order_vals = {
                'name': original_order.name + str(" - ") + str(name[0]),
                'partner_id': original_order.partner_id.id,
                'order_line': [],
                'company_id': company_id,
                'sale_order_template_id': original_order.sale_order_template_id.id,
                'pricelist_id': original_order.pricelist_id.id,
                'validity_date': original_order.validity_date,
                'date_order': original_order.date_order,
                'payment_term_id': original_order.payment_term_id.id,
                'picking_policy': original_order.picking_policy,
                'user_id': original_order.user_id.id,
                'splitted': 1,
                'condicion_venta': original_order.condicion_venta,
                'note': original_order.note,
                'internal_notes': original_order.internal_notes,
                'available_condiciones': False,
                'condicion_m2m': original_order.condicion_m2m.id,
                'condicion_m2m_numeric': original_order.condicion_m2m_numeric,
                'state': 'sale',
                'client_order_ref': original_order.company_id.name,
                'special_price': original_order.special_price,
            }
            # _logger.info(f"Nueva SO: {new_order_vals}")

            for line_index, line in enumerate(original_order.order_line):
                quantity = round(line.product_uom_qty * self.percentage / 100)

                # IMPUESTOS DEL PRODUCTO
                # valid_taxes = line.product_id.taxes_id.filtered(lambda tax: tax.company_id.id == company_id)
                valid_taxes = line.tax_id.filtered(lambda tax: tax.company_id.id == company_id)
                # _logger.info(f"Impuestos de línea: {valid_taxes.ids}")

                new_order_line_vals = (0, 0, {
                      'product_id': line.product_id.id,
                      'product_uom_qty': quantity,
                      'product_uom': line.product_uom.id,
                      #'product_packaging_qty': quantity / line.product_packaging_id.qty if line.product_packaging_id else 0,
                      'product_packaging_qty': line.product_packaging_qty,
                      'product_packaging_id': line.product_packaging_id.id,
                      'price_unit': line.price_unit,
                      'tax_id': [(6, 0, valid_taxes.ids)],
                      'discount': line.discount,
                })
                new_order_vals['order_line'].append(new_order_line_vals)
                # _logger.info(f"Valores de nueva línea: {new_order_line_vals}")

            new_order = self.env['sale.order'].create(new_order_vals)
            new_orders += new_order

        for original_line in original_order.order_line:
            original_quantity = original_line.product_uom_qty
            new_quantity = sum(line.product_uom_qty for new_order in new_orders for line in new_order.order_line if line.product_id == original_line.product_id)
            if abs(new_quantity - original_quantity) > 0.01:
                difference = original_quantity - new_quantity

                # POR CASO DE DIFERENCIA MAYOR A CANTIDAD ORIGINAL
                difference = int(-original_quantity if difference < 0 and abs(difference) > original_quantity else difference)

                _logger.info(f"Diferencia: {difference}")

                for new_order in new_orders:
                    for line in new_order.order_line:
                        if line.product_id == original_line.product_id:
                            _logger.info(f"line.product_uom_qty 1 %%%: {line.product_uom_qty}")
                            # VAMOS CON TRY
                            try:
                                line.product_uom_qty += difference
                            except Exception as e:
                                _logger.error(f"Error adjusting quantity for {line.product_id.name}: {e}")
                                continue
                            # line.product_uom_qty += difference
                            _logger.info(f"line.product_uom_qty 2 %%%: {line.product_uom_qty}")
                            break
                    break

        # ESTO NO SIRVE CON EL BOTÓN DE CONFIRMACIÓN, PORQUE PRIMERO CONFIRMA,
        # ENTONCES LUEGO NO PUEDE ELIMINAR: COMENTAMOS LÍNEAS
        # for new_order in new_orders:
        #     for line in new_order.order_line:
        #         if line.product_uom_qty == 0:
        #             new_order.write({'order_line': [(3, line.id)]})

        original_order.action_cancel()
        original_order.toggle_active()

        for new_order in new_orders:
            new_order.write({'origin': original_order.name})

        for new_order in new_orders:
            if new_order.amount_total == 0:
                new_order.action_cancel()
                new_order.unlink()

    
    class SaleOrderSettings(models.Model):
        _name = 'sale.order.settings'

        name = fields.Char('Nombre')
        carga_bultos = fields.Boolean(string="Carga por bultos", default=True)
        carga_unidades = fields.Boolean(string="Carga por unidades")
        activo = fields.Boolean("Activo", default=False)

        @api.onchange('carga_bultos')
        def _onchange_carga_bultos(self):
            for record in self:
                if record.carga_bultos:
                    record.carga_unidades = False

        @api.onchange('carga_unidades')
        def _onchange_carga_unidades(self):
            for record in self:
                if record.carga_unidades:
                    record.carga_bultos = False