from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    packaging_qty = fields.Float(string='Cantidad de Bultos' ,compute='get_bultos')
    qty_delivered = fields.Float(string='Entregados',compute='get_bultos',store=True)
    qty_invoiced = fields.Float(string='Facturados',compute='get_bultos')
    sale_order_lines = fields.Float(string='Lineas de Pedido',compute='get_lines')

    def get_lines(self):
        order_lines = 0
        for order in self:      
            for line in order.order_line:      
                order_lines = len(order.order_line)
            order.update({'sale_order_lines': order_lines })
            
    def get_bultos(self):
        self.packaging_qty = 0
        for order in self:      
            bultos = 0.0       
            delivered = 0.0       
            invoiced = 0.0       
            for line in order.order_line:      
                 if line.product_packaging_qty:
                    if not line.product_packaging_id :
                        if line.product_template_id.packaging_ids and order.state in ['draft']: # and (line.product_uom_qty == 0 or not line.product_uom_qty):
                            line.write(
                                {
                                    'product_uom_qty': int(line.product_template_id.packaging_ids[0].qty * line.product_packaging_qty),
                                    'product_packaging_id': line.product_template_id.packaging_ids[0],
                                })
                    try:
                        invoiced += line.qty_invoiced  / line.product_packaging_id.qty
                        delivered += line.qty_delivered / line.product_packaging_id.qty
                    except:
                        continue
                    bultos += line.product_packaging_qty
            order.update({'packaging_qty': bultos ,'qty_delivered':delivered,'qty_invoiced':invoiced})

