from odoo import models, fields, api, _


class ChinaPurchaseInherit(models.Model):
    _inherit = 'china.purchase'

    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")