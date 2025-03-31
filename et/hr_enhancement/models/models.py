from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def action_open_my_profile(self):
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if employee:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Mi Perfil',
                'res_model': 'hr.employee',
                'view_mode': 'form',
                'res_id': employee.id,
                'target': 'current',
            }
        else:
            return {'type': 'ir.actions.act_window_close'}
