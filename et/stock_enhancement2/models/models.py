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
    
    order_type = fields.Many2one(
        comodel_name='condicion.venta',
        string='Condición de Venta',
        related='sale_id.condicion_m2m',
        store=True
    )