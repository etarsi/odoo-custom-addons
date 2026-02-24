from odoo import models, fields, api


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")
    task_id = fields.Many2one(string="Tarea", comodel_name="wms.task")