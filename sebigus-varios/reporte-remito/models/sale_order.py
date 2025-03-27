from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    packaging_qty = fields.Float(string='Cantidad de Bultos',compute='get_bultos')
    sale_order_lines = fields.Float(string='Lineas de Pedido',compute='get_lines')

    def get_lines(self):
        for order in self:      
            for line in order.order_line:      
                order.update({'sale_order_lines': len(order.order_line) })
            
    def get_bultos(self):
        for order in self:      
            bultos = 0.0       
            for line in order.order_line:      
                 if line.product_packaging_qty:
                    if not line.product_packaging_id :
                        if line.product_template_id.packaging_ids:
                            line.write(
                                {
                                    'product_uom_qty': line.product_template_id.packaging_ids[0].qty * line.product_packaging_qty,
                                    'product_packaging_id': line.product_template_id.packaging_ids[0],
                                })

                    bultos += line.product_packaging_qty
            order.update({'packaging_qty': bultos })

