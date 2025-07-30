from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrEmployeeSalary(models.Model):
    _name = 'hr.employee.salary'
    _description = 'Salary History Record'

    employee_id = fields.Many2one(
        'hr.employee', 
        string="Empleado", 
        required=True
    )
    old_salary = fields.Float(
        string="Salario anterior", 
        readonly=True
    )
    new_salary = fields.Float(
        string="Nuevo salario", 
        required=True
    )
    percentage_increase = fields.Float(
        string="Porcentaje de incremento (%)", 
        readonly=True
    )
    salary_date = fields.Datetime(
        string="Fecha de cambio",
        default=fields.Datetime.now, 
        readonly=True
    )
    user_id = fields.Many2one(
        'res.users', 
        string="Registrado por", 
        default=lambda self: self.env.user, 
        readonly=True
    )

    @api.model
    def create(self, vals):
        # Obtener salario anterior
        employee = self.env['hr.employee'].browse(vals['employee_id'])
        old_salary = employee.contract_id.wage if employee.contract_id else 0.0
        vals['old_salary'] = old_salary
        # Calcular porcentaje de incremento
        new_salary = vals.get('new_salary', 0.0)
        if old_salary and new_salary > old_salary:
            vals['percentage_increase'] = ((new_salary - old_salary) / old_salary) * 100
        else:
            vals['percentage_increase'] = 0.0
        return super().create(vals)
