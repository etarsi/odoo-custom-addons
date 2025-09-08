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
    quantity_delivered = fields.Integer()
    bultos = fields.Float()
    uxb = fields.Integer()
    type = fields.Selection(selection=[('reserve', 'Reserva'), ('delivery', 'Entrega')])

    @api.model
    def create(self, vals):
        
        records = super().create(vals)

        for record in records:
            if record.type == 'reserve':
                record.stock_erp.increase_comprometido_unidades(record.quantity)
            elif record.type == 'delivery':
                record.stock_erp.decrease_fisico_unidades(record.quantity)
                record.stock_erp.decrease_comprometido_unidades(record.quantity)
        return records

    def unreserve_stock(self):
        for record in self:
            if record.type == 'reserve':
                if not record.sale_id.picking_ids:
                    continue

                partial_quantity = 0
                total_qty_to_unlink = record.quantity
                moves_to_unlink = []
                pickings_to_check = set()

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
                        pickings_to_check.add(move.picking_id)
                        move.state = 'draft'
                        move.unlink()
                        record.check_picking(pickings_to_check)
                    record.stock_erp.decrease_comprometido_unidades(record.quantity)
                    record.update_sale_orders()
                    record.unlink()

    def update_sale_orders(self):
        for record in self:
            sales_lines_to_update = record.stock_erp.move_lines.mapped('sale_line_id')
            if sales_lines_to_update:
                for line in sales_lines_to_update:
                    line.update_stock_erp()

    def check_picking(self, pickings):
        for p in pickings:
            if not p.move_ids_without_package:
                p.state = 'draft'
                p.unlink()


    def unreserve_sale_line(self, move):
        sale_line = move.sale_line_id
        if sale_line:
            if sale_line.invoice_lines:
                raise UserError(f"No se puede borrar la línea de venta {sale_line.name} porque ya fue facturada.")            
            sale_line.product_uom_qty = 0
            sale_line.is_cancelled = True