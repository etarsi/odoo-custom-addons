from odoo import models, fields, api, _
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError, AccessError
import logging
import math
import requests
from itertools import groupby
from datetime import timedelta

class StockMovesERP(models.Model):
    _name = 'stock.moves.erp'

    
    name = fields.Char()
    stock_erp = fields.Many2one('stock.erp')
    sale_id = fields.Many2one('sale.order')
    sale_line_id = fields.Many2one('sale.order.line')
    picking_id = fields.Many2one('stock.picking')
    product_id = fields.Many2one('product.product')
    quantity = fields.Integer()
    bultos = fields.Float()
    uxb = fields.Integer()

    def unreserve_stock(self):
        for record in self:
            partial_quantity = 0
            if record.sale_id.picking_ids:

                for picking in record.sale_id.picking_ids:
                    if picking.move_ids_without_package:
                        for move in picking.move_ids_without_package:
                            if move.product_id == record.product_id.id:
                                if picking.state_wms != 'no':
                                    raise UserError(f'No se puede liberar la cantidad comprometida ({record.sale_id}) porque las unidades están siendo preparadas o ya han sido preparadas en la transferencia {record.picking_id}.')
                                else:
                                    if move.product_uom_qty < record.quantity:
                                        partial_quantity += move.product_uom_qty
                                    elif record.quantity == move.product_uom_qty or record.quantity == partial_quantity:                                        
                                        # record.unreserve_sale_line()
                                        record.unlink()
    

    # def unreserve_sale_line(self):
    #     for record in self:
            