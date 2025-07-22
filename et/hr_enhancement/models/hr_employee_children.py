from odoo import models, fields, api

class HrEmployeeChildren(models.Model):
    _name = 'hr.employee.children'

    parent_id = fields.Many2one('hr.employee', required=True, string='Padre/Madre')
    name = fields.Char('Nombre y Apellido', required=True)
    age = fields.Integer('Edad', required=True)
    dni = fields.Char('DNI', required=True)
    birth_date = fields.Date('Fecha de Nacimiento', required=True)
    photo_dni = fields.Binary('Foto DNI', required=True)
    gender = fields.Selection([
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('non_binary', 'No binario')
    ], string='Género', required=True)
