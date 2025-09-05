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
            if not record.sale_id.picking_ids:
                continue

            partial_quantity = 0
            total_qty_to_unlink = record.quantity
            moves_to_unlink = []

            for picking in record.sale_id.picking_ids:
                if picking.state_wms != 'no':
                    raise UserError(
                        f'No se puede liberar la cantidad comprometida ({record.sale_id.name}) porque las unidades están siendo preparadas o ya fueron preparadas en la transferencia {picking.name}.'
                    )

                for move in picking.move_ids_without_package:
                    if move.product_id.id != record.product_id.id:
                        continue

                    if move.product_uom_qty + partial_quantity <= total_qty_to_unlink:
                        moves_to_unlink.append(move)
                        partial_quantity += move.product_uom_qty

            if partial_quantity >= total_qty_to_unlink:
                for move in moves_to_unlink:
                    record.unreserve_sale_line(move)
                    move.state = 'draft'
                    move.unlink()
                record.unlink()



    def unreserve_sale_line(self, move):
        sale_line = move.sale_line_id
        if sale_line:
            if sale_line.invoice_lines:
                raise UserError(f"No se puede borrar la línea de venta {sale_line.name} porque ya fue facturada.")            
            sale_line.product_uom_qty = 0
            sale_line.is_cancelled = True