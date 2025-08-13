from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime

class HrEmployeeSalary(models.Model):
    _name = 'hr.employee.salary'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Historial de Sueldos de Empleado'

    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True, tracking=True)
    date = fields.Date(string="Fecha", required=True, default=fields.Date.today, tracking=True)
    actual_salary = fields.Float(string="Sueldo Actual", compute="_compute_actual_salary", store=True, tracking=True)
    real_salary = fields.Float(string="Salario Real", store=True, tracking=True)
    gross_salary = fields.Float(string="Sueldo Bruto", required=True, tracking=True)
    bank_salary = fields.Float(string="Sueldo por Banco", required=True, tracking=True)
    percentage_increase = fields.Float(string="Porcentaje de Incremento",
                                        compute="_compute_percentage_increase", store=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('expired', 'Expirado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True)
    tipo_ajuste = fields.Selection([
        ('paritaria', 'Paritaria'),
        ('acuerdo', 'Acuerdo Empresa'),
        ('promocion', 'Promoción'),
        ('ajuste', 'Ajuste General'),
        ('otro', 'Otro')
    ], string="Tipo de Ajuste", required=True, tracking=True)
    notes = fields.Text(string="Notas")

    @api.depends('gross_salary', 'date', 'actual_salary')
    def _compute_percentage_increase(self):
        for rec in self:
            # Buscar el salario anterior (menor fecha)
            employee_salary = self.env['hr.employee.salary'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', 'in', ['confirmed', 'expired']),
                ('date', '<', rec.date)
            ], order='date desc', limit=1)
            if employee_salary and employee_salary.gross_salary:
                rec.percentage_increase = ((rec.gross_salary - employee_salary.gross_salary) / employee_salary.gross_salary) * 100
            else:
                rec.percentage_increase = 0.0
                
    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError('Solo se puede confirmar un ajuste salarial en estado Borrador.')
            record.state = 'confirmed'
            #cuando esta confirmado, se marca los demas registros como expirados y que no modifiquen el sueldo actual
            self.env['hr.employee.salary'].search([
                ('employee_id', '=', record.employee_id.id),
                ('id', '!=', record.id),
                ('state', '=', 'confirmed'),
            ]).write({'state': 'expired'})

    def action_cancelled(self):
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError('Solo se puede cancelar un ajuste salarial en estado Aprobado.')
            record.state = 'cancelled'

    def action_draft(self):
        for record in self:
            if record.state not in ['confirmed']:
                raise ValidationError('Solo se puede restablecer a Borrador un ajuste salarial en estado Confirmado.')
            record.state = 'draft'

    def unlink(self):
        for record in self:
            if record.state not in ['draft', 'cancelled']:
                raise ValidationError('No se puede eliminar un ajuste salarial que no esté en estado Borrador o Cancelado.')
        return super(HrEmployeeSalary, self).unlink()

    @api.depends('employee_id', 'employee_id.salary_ids', 'employee_id.salary_ids.state', 'employee_id.salary_ids.date', 'employee_id.salary_ids.real_salary')
    def _compute_actual_salary(self):
        for rec in self:
            actual = 0.0
            emp = rec.employee_id
            if emp:
                confirmed = emp.salary_ids.filtered(lambda s: s.state == 'confirmed')
                if confirmed:
                    # opción A: ordenar y tomar el más reciente
                    last = confirmed.sorted(lambda s: s.date)[-1]
                    actual = last.real_salary or 0.0
            rec.actual_salary = actual

