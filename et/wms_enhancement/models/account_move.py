from odoo import models, fields, api, _


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")
    task_id = fields.Many2one(string="Tarea", comodel_name="wms.task")

    def action_open_wms_task(self):
       self.ensure_one()
       if not self.task_id:
           return False

       return {
           'type': 'ir.actions.act_window',
           'name': _('Tarea WMS'),
           'res_model': 'wms.task',
           'view_mode': 'form',
           'res_id': self.task_id.id,
           'target': 'current',
        }
    

    def sacar_iva_21(self):
        for record in self:
            for line in record.invoice_line_ids:
                new_price = line.price_unit / 1.21
                line.write({
                    'price_unit': new_price
                })

            record._recompute_dynamic_lines()