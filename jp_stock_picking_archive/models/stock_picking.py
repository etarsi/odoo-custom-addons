from odoo import fields, models


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = 'stock.picking'

    active = fields.Boolean(default=True)
