from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    direccion_casa = fields.Char('Dirección')
    entre_calles = fields.Char('Entre Calles')
    localidad = fields.Char('Localidad')
    partido = fields.Char('Partido')
    cp_code = fields.Char('CP')
    dni = fields.Integer('DNI')
    cuil = fields.Integer('CUIL')
    dni_fotos = fields.Char('Foto DNI')
    hijos = fields.Boolean('Hijos', default=False)
    hijos_datos = fields.One2many('employee.children', string='Hijos')    
    alta_afip = fields.Date('Fecha de Alta AFIP')
    licencias = fields.One2many('employee.license','employee_id', string="Licencias")
    
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
