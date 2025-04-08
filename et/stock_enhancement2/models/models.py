from odoo import models, fields, api


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    state_wms = fields.Selection([
        ('closed','Enviado y recibido'),
        ('done','Enviado'),
        ('no','No enviado'),
        ('error','Error envio'),
        ('pending', 'Pendiente')
        ],
        string='Estado WMS',
        default='no',
        copy=False,
        tracking=True
        )
    
    # order_type = fields.Many2one(
    #     comodel_name='condicion.venta',
    #     string='Condición de Venta',
    #     related='sale_id.condicion_m2m',
    #     store=True
    # )

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