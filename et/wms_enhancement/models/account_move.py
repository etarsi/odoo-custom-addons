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
        for move in self:
            # 1) cambiar price_unit sin validar balance en cada write
            for line in move.invoice_line_ids:
                line.with_context(check_move_validity=False).write({
                    'price_unit': line.price_unit / 1.21
                })

            # 2) recomputar todo lo dinámico (líneas contables, totales, vencimientos)
            move.with_context(check_move_validity=False)._recompute_dynamic_lines()