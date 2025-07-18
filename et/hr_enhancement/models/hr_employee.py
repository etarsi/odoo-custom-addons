from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    ingreso_date = fields.Date(string='Fecha de Ingreso', required=True)
    salida_date = fields.Date(string='Fecha de Salida')
    position = fields.Char(string='Puesto', required=True)
    dni = fields.Char(string='DNI', required=True)
    dni_foto_front = fields.Binary('Foto DNI')
    dni_foto_back = fields.Binary('Foto DNI 2')
    cuil = fields.Char(string='CUIL', required=True)
    celular = fields.Char(string='Celular', required=True)
    
    #datos familiares
    spouse_dni = fields.Char(string='DNI del Cónyuge')
    is_children = fields.Boolean(string='Tiene Hijos', default=False)
    #relación de uno a muchos para los hijos
    children_ids = fields.One2many('hr.legajo.children', 'legajo_id', string='Hijos')
    #familiar a cargo
    dependent_name = fields.Char(string='Nombre del Familiar a Cargo')
    dependent_dni = fields.Char(string='DNI del Familiar a Cargo')

    #datos de cuenta bancaria
    bank = fields.Char(string='Banco', required=True)
    nro_account = fields.Char(string='Número de Cuenta', required=True)
    cbu = fields.Char(string='CBU', required=True)
    alias = fields.Char(string='Alias', required=True)

    #que monto de sueldo sea una relación de uno a muchos
    salary_ids = fields.One2many('hr.legajo.salary', 'employee_id', string='Sueldos')
    salary_count = fields.Integer(string='Cantidad de Sueldos', compute='_compute_salary_count')
    alta_afip = fields.Date('Fecha de Alta AFIP')
    
    #hr location
    location_id = fields.Many2one('hr.location', string='Dirección', ondelete='set null', index=True, copy=False)
    
    _sql_constraints = [
        ('unique_dni', 'UNIQUE(dni)', 'El DNI debe ser único por empleado.'),
        ('unique_cuil', 'UNIQUE(cuil)', 'El CUIL debe ser único por empleado.'),
        ('unique_celular', 'UNIQUE(celular)', 'El Celular debe ser único por empleado.'),
        ('unique_cbu', 'UNIQUE(cbu)', 'El CBU debe ser único por empleado.'),
        ('unique_alias', 'UNIQUE(alias)', 'El Alias debe ser único por empleado.'),
        ('unique_account', 'UNIQUE(nro_account)', 'El Número de Cuenta debe ser único por empleado.'),
    ]
    
    @api.depends('salary_ids')
    def _compute_salary_count(self):
        for record in self:
            record.salary_count = len(record.salary_ids)

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


