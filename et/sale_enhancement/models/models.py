from odoo import models, fields, api

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    global_discount = fields.Float('Descuento', default=0)

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