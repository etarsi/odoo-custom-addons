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
    sale_line_id = fields.Many2one('sale.order.line', ondelete='set null')
    partner_id = fields.Many2one('res.partner')
    picking_id = fields.Many2one('stock.picking')
    product_id = fields.Many2one('product.product')
    quantity = fields.Integer()
    quantity_delivered = fields.Integer("Cantidad entregada")
    bultos = fields.Float(compute="_compute_bultos")
    uxb = fields.Integer()
    type = fields.Selection(selection=[('reserve', 'Reserva'), ('delivery', 'Entrega'), ('preparation', 'Preparación')])
    
    #SOLO PARA SABER QUE TRANSFERENCIAS ESTAN HECHAS O CANCELADAS
    # transfer_picking_ids = fields.Many2many(
    #     "stock.picking",
    #     compute="_compute_transfers",
    #     string="Transferencias (Remitos)",
    #     store=False,
    # )

    # transfer_quantity_done = fields.Integer(
    #     compute="_compute_transfers",
    #     string="Cantidad Hechas",
    #     store=True,
    # )
    # transfer_quantity_cancel = fields.Integer(
    #     compute="_compute_transfers",
    #     string="Cantidad Canceladas",
    #     store=True,
    # )
    # transfer_quantity_comprometida = fields.Integer(
    #     compute="_compute_transfers",
    #     string="Cantidad Comprometidas",
    #     store=True,
    # )

    # @api.depends(
    #     "sale_line_id",
    #     "product_id",
    #     "sale_line_id.move_ids",
    #     "sale_line_id.move_ids.state",
    #     "sale_line_id.move_ids.product_id",
    #     "sale_line_id.move_ids.picking_id",
    #     "sale_line_id.move_ids.picking_id.state",
    # )
    # def _compute_transfers(self):
    #     Picking = self.env["stock.picking"]
    #     for rec in self:
    #         pickings = Picking.browse()
    #         quantity_cancel = 0
    #         quantity_done = 0
    #         quantity_comprometida = 0
    #         if rec.sale_line_id and rec.type=='reserve':
    #             moves = rec.sale_line_id.move_ids

    #             # asegurar el producto (por si tu modelo permite inconsistencias)
    #             if rec.product_id:
    #                 moves = moves.filtered(lambda m: m.product_id.id == rec.product_id.id)

    #             # quedarnos con transferencias reales (y típicamente de salida)
    #             moves = moves.filtered(
    #                 lambda m: m.picking_id
    #                 and m.picking_id.picking_type_id.code == "outgoing"
    #             )
    #             # sacar del moves las cantidades canceladas y hechas
    #             for move in moves:
    #                 quantity_cancel += move.product_uom_qty if move.picking_id.state == "cancel" else 0
    #                 quantity_comprometida += move.product_uom_qty if move.picking_id.state not in ["cancel", "done"] else 0
    #                 quantity_done += move.product_uom_qty if move.picking_id.state == "done" else 0
                    

    #             # pickings únicos
    #             picking_ids = list(set(moves.mapped("picking_id").ids))
    #             pickings = Picking.browse(picking_ids)

    #         rec.transfer_picking_ids = [(6, 0, pickings.ids)]
    #         rec.transfer_quantity_done = quantity_done
    #         rec.transfer_quantity_cancel = quantity_cancel
    #         rec.transfer_quantity_comprometida = quantity_comprometida

    # def action_view_transfers(self):
    #     self.ensure_one()
    #     return {
    #         "name": "Transferencias",
    #         "type": "ir.actions.act_window",
    #         "res_model": "stock.picking",
    #         "view_mode": "tree,form",
    #         "domain": [("id", "in", self.transfer_picking_ids.ids)],
    #     }

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
                if record.sale_line_id.qty_delivered > 0:
                    if  record.sale_line_id.product_uom_qty == (record.sale_line_id.qty_delivered + 10):
                        raise UserError(f"No se puede borrar la línea de venta {record.sale_line_id.name} porque ya tiene cantidades entregadas.")
                    
                    #raise UserError(f"No se puede borrar la línea de venta {record.sale_line_id.name} porque ya tiene cantidades entregadas.")
                else:    
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