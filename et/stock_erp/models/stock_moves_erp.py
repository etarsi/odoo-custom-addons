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
    partner_id = fields.Many2one('res.partner')
    picking_id = fields.Many2one('stock.picking')
    product_id = fields.Many2one('product.product')
    quantity = fields.Integer()
    quantity_delivered = fields.Integer()
    bultos = fields.Float(compute="_compute_bultos")
    uxb = fields.Integer()
    type = fields.Selection(selection=[('reserve', 'Reserva'), ('delivery', 'Entrega'), ('preparation', 'Preparación')])

    @api.model
    def create(self, vals):
        
        records = super().create(vals)

        for record in records:
            if record.type == 'reserve':
                record.stock_erp.increase_comprometido_unidades(record.quantity)
            elif record.type == 'delivery':
                record.stock_erp.decrease_fisico_unidades(record.quantity)
                record.stock_erp.decrease_comprometido_unidades(record.quantity)
            elif record.type == 'preparation':
                record.stock_erp.decrease_entregable_unidades(record.quantity)

            record.update_sale_orders()

        return records

    def undo_preparation(self):
        for record in self:
            if record.type == 'preparation':
                record.stock_erp.increase_entregable_unidades(record.quantity)
                record.unlink()


    def unreserve_stock(self):
        for record in self:
            stock_in_preparation = self.env['stock.moves.erp'].search([
                ('sale_line_id', '=', record.sale_line_id.id), 
                ('product_id', '=', record.product_id.id), 
                ('type', '=', 'preparation')
            ], limit=1)

            if stock_in_preparation:
                raise UserError(f'No se puede liberar el stock del pedido {record.sale_id.name} porque se está preparando en la transferencia {stock_in_preparation.picking_id.name}')
            
            else:
                record.cancel_sale_line()
                record.cancel_picking_line()
                record.stock_erp.decrease_comprometido_unidades(record.quantity)
                record.update_sale_orders()
                record.unlink()


    def unreserve_stock2(self):
        for record in self:
            if record.type == 'reserve':

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
                    record.stock_erp.increase_disponible_unidades(record.quantity)
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

    def cancel_sale_line(self):
        for record in self:
            if record.sale_line_id:
                if record.sale_line_id.invoice_lines:
                    raise UserError(f"No se puede borrar la línea de venta {record.sale_line_id.name} porque ya fue facturada.")            
                record.sale_line_id.product_uom_qty = 0
                record.sale_line_id.is_cancelled = True

    
    def cancel_picking_line(self):
        for record in self:
            if record.sale_line_id.move_ids:
                for move in record.sale_line_id.move_ids:
                    move.state = 'draft'
                    move.quantity_done = 0
                    move.unlink()


    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if record.quantity == record.quantity_delivered:
                record.unlink()
        return res

    @api.depends('quantity')
    def _compute_bultos(self):
        for record in self:
            if record.uxb:
                record.bultos = record.quantity / record.uxb
            else:
                record.bultos = 0