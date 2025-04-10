from odoo import models, fields, api

class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    wms_date = fields.Date(string="Fecha WMS")
    has_rodado = fields.Boolean(string="Rodados", compute="_compute_has_rodado", store=True)

    @api.depends('move_ids_without_package')
    def _compute_has_rodado(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.category_id.parent_id.id == 320:
                    record.has_rodado = True


    def enviar(self):
        res = super().enviar()
        for record in self:
            record.wms_date = fields.Date.today()

        return res

    def ajustar_fecha(self):
        for record in self:
            record.wms_date = fields.Date.today()

    def split_auto(self):
        for picking in self:
            selected_moves = self.env['stock.move']
            line_count = 0
            bulto_count = 0

            for move in picking.move_ids_without_package:
                if move.product_available_percent == 100:
                    if line_count > 24 or bulto_count >= 15:
                        break
                    
                    bulto_qty = bulto_count + move.product_packaging_qty
                    if bulto_qty <= 20:      
                        line_count += 1
                        bulto_count += move.product_packaging_qty
                        selected_moves |= move

            if selected_moves:
                return picking._split_off_moves(selected_moves)
        return False