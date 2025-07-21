from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class HrEmployeeSalary(models.Model):
    _name = 'hr.employee.salary'
    _description = 'Salario del Empleado'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    salary_date = fields.Date(string='Fecha de Salario', required=True)
    amount = fields.Float(string='Monto', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True)
    description = fields.Text(string='Descripción')
    #estado del empleado salary
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('in_progress', 'En Proceso'),
        ('approved', 'Aprobado'),
        ('cancelled', 'Cancelado'),
        ('archived', 'Archivado'),
    ], string='Estado', default='draft', required=True)
    porcentage_increase = fields.Float(string='Porcentaje de Aumento', default=0.0)
    increase_date = fields.Date(string='Fecha de Aumento')
    increase_reason = fields.Char(string='Motivo del Aumento')
    decrease_date = fields.Date(string='Fecha de Disminución')
    decrease_reason = fields.Char(string='Motivo de la Disminución')
    
