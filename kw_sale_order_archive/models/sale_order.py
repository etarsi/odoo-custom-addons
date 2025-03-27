from odoo import fields, models


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    active = fields.Boolean(default=True)
