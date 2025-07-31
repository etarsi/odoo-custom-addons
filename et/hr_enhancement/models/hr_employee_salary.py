from odoo import models, fields, api

class HrEmployeeSalary(models.Model):
    _name = 'hr.employee.salary'
    _description = 'Historial de Sueldos de Empleado'

    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True, ondelete='cascade')
    date = fields.Date(string="Fecha", required=True, default=fields.Date.today)
    amount = fields.Float(string="Sueldo Bruto", required=True)
    percentage_increase = fields.Float(string="Porcentaje de Incremento", compute="_compute_percentage_increase", store=True)
    notes = fields.Char(string="Notas")
    tipo_ajuste = fields.Selection([
        ('paritaria', 'Paritaria'),
        ('acuerdo', 'Acuerdo Empresa'),
        ('promocion', 'Promoción'),
        ('ajuste', 'Ajuste General'),
        ('otro', 'Otro')
    ], string="Tipo de Ajuste")

    @api.depends('employee_id', 'amount', 'date')
    def _compute_percentage_increase(self):
        for rec in self:
            # Buscar el salario anterior (menor fecha)
            prev = self.env['hr.employee.salary'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('date', '<', rec.date)
            ], order='date desc', limit=1)
            if prev and prev.amount:
                rec.percentage_increase = ((rec.amount - prev.amount) / prev.amount) * 100
            else:
                rec.percentage_increase = 0.0
