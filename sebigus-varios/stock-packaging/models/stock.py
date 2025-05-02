from odoo import tools, models, fields, api, _
import base64
import logging
_logger = logging.getLogger(__name__)

class StockTransfer(models.Model):
    _inherit = "stock.picking"
    packaging_qty = fields.Float(string='Cantidad de Bultos' ,compute='sum_bultos', group_operator='sum',store=True)
    available_pkg_qty = fields.Float(string='Bultos Disponibles' ,compute='sum_bultos', group_operator='sum')
    available_percent = fields.Float(string='Porc Disponible' ,compute='sum_bultos',store=True,  group_operator='avg')
    sale_order_lines = fields.Float(string='Lineas de Pedido',compute='get_lines', group_operator='sum')

    def get_lines(self):
        for order in self:      
            order.update({'sale_order_lines': len(order.move_ids_without_package)})

    def sum_bultos(self):
        for order in self:      
            bultos = 0.0       
            bultos_disp = 0.0       
            qty_done=False
            for line in order.move_ids_without_package:      
                if line.product_packaging_id:
                    if line.quantity_done > 0:
                        qty_done=True
            for line in order.move_ids_without_package:      
                if line.product_packaging_id:
                    bultos_disp += line.quantity_done / line.product_packaging_id.qty 
                    bultos += line.product_uom_qty / line.product_packaging_id.qty 
                    ba = line.quantity_done   / line.product_packaging_id.qty
                    b =  line.product_uom_qty / line.product_packaging_id.qty
                else:
                    b = 0
                    ba = 0
                bp = (line.quantity_done  / line.product_uom_qty) * 100 if line.product_uom_qty > 0 else 0
                line.update({'product_packaging_qty':b,'product_available_pkg_qty':ba,'product_available_percent':bp})
            order.update({'packaging_qty': bultos,'available_pkg_qty': bultos_disp,'available_percent': (bultos_disp / bultos) * 100 if bultos > 0 else 0})

class StockMove(models.Model):
    _inherit = "stock.move"
    product_packaging_qty = fields.Float(string='Bultos', compute='bultos',store=True, group_operator='sum')
    product_available_pkg_qty = fields.Float(string='Bultos Disponibles' ,compute='bultos',store=True, group_operator='sum')
    product_available_percent = fields.Float(string='Porc Disponible' ,compute='bultos',store=True, group_operator='avg')

    def bultos(self):
        for line in self:
            if line.product_packaging_id:
                ba = line.quantity_done   / line.product_packaging_id.qty
                b  = line.product_uom_qty / line.product_packaging_id.qty
            else:
                b = 0
                ba = 0

            try:
                bp = (line.quantity_done  / line.product_uom_qty) * 100
            except:
                bp = 0
            line.update({'product_packaging_qty':b,'product_available_pkg_qty':ba,'product_available_percent':bp})

