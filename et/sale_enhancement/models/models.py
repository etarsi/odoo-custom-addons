from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    order_subtotal = fields.Float('Subtotal', compute='_compute_subtotal', readonly=True)
    global_discount = fields.Float('Descuento', default=0)

    @api.depends('amount_tax', 'amount_untaxed')
    def _compute_subtotal(self):
        for record in self:
            if record.order_line:
                if record.order_line[0].tax_id.id in [62, 185, 309, 433]:
                    record.order_subtotal = record.amount_untaxed * 1.21
                else:
                    record.order_subtotal = record.amount_untaxed

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
            record.packaging_qty
            for line in record.order_line:
                record.packaging_qty += line.product_packaging_qty

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

    ## TEMPORAL ### HACER UN DEFAULT VALUE PARA ESTOS CAMPOS
    @api.onchange('product_id')
    def _onchange_product(self):
        for record in self:
            if record.product_id:
                record.discount = record.order_id.global_discount              
                packaging_ids = record.product_id.packaging_ids
                if packaging_ids:
                    # record.product_packaging_id = packaging_ids[0]
                    record.write(
                                {
                                    'product_uom_qty': int(packaging_ids[0].qty * record.product_packaging_qty),
                                    'product_packaging_id': packaging_ids[0],
                                })
                    
    ## DESHABILITAR ADVERTENCIA DE UNIDAD X BULTO                    
    @api.onchange('product_packaging_id')
    def _onchange_product_packaging_id(self):
        return