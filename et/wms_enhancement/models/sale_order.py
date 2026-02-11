from odoo import models, fields, api


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'


    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")