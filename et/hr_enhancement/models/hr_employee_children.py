from odoo import models, fields, api

class HrEmployeeChildren(models.Model):
    _name = 'hr.employee.children'
    _rec_name = 'name'

    employee_id = fields.Many2one('hr.employee', required=True, string='Padre/Madre')
    name = fields.Char('Nombre y Apellido', required=True)
    age = fields.Integer('Edad', required=True)
    dni = fields.Char('DNI', required=True)
    birth_date = fields.Date('Fecha de Nacimiento', required=True)
    dni_photo_front = fields.Binary('Foto DNI', required=True)
    dni_photo_back = fields.Binary('Foto DNI', required=True)
    gender = fields.Selection([
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('other', 'Otro')
    ], string='Género', required=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('approved', 'Aprobado')], string='Estado', default='draft', required=True)
