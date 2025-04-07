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
    # hijos_datos = fields.One2many('employee.children', 'parent_id', string='Hijos')    
    alta_afip = fields.Date('Fecha de Alta AFIP')
    # licencias = fields.One2many('employee.license', 'employee_id', string="Licencias")
    licencia_count = fields.Integer(string="Cantidad de Licencias", compute='_compute_licencia_count')

    @api.depends('licencias')
    def _compute_licencia_count(self):
        for rec in self:
            rec.licencia_count = len(rec.licencias)
    
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

    def action_view_licencias(self):
        self.ensure_one()
        return {
            'name': 'Licencias',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.license',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
