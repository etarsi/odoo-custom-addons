from odoo import models, fields, api


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")