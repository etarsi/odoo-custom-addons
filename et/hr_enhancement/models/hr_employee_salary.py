from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime

class HrEmployeeSalary(models.Model):
    _name = 'hr.employee.salary'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Historial de Sueldos de Empleado'

    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True, ondelete='cascade')
    date = fields.Date(string="Fecha", required=True, default=fields.Date.today)
    amount = fields.Float(string="Sueldo Bruto", required=True)
    percentage_increase = fields.Float(string="Porcentaje de Incremento", compute="_compute_percentage_increase", store=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('approved', 'Aprobado'),
        ('expired', 'Expirado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True)
    notes = fields.Char(string="Notas")
    tipo_ajuste = fields.Selection([
        ('paritaria', 'Paritaria'),
        ('acuerdo', 'Acuerdo Empresa'),
        ('promocion', 'Promoción'),
        ('ajuste', 'Ajuste General'),
        ('otro', 'Otro')
    ], string="Tipo de Ajuste")
    is_current = fields.Boolean(string="Es el Sueldo Vigente", default=False)
    
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        # Buscar el empleado del usuario actual
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if employee:
            res['employee_id'] = employee.id
        return res

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
                
    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError('Solo se puede confirmar un ajuste salarial en estado Borrador.')
            record.state = 'confirmed'

    def action_approve(self):
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError('Solo se puede aprobar un ajuste salarial en estado Confirmado.')
            record.state = 'approved'
            #colocar expirado a los anteriores ajustes
            previous_salaries = self.env['hr.employee.salary'].search([
                ('employee_id', '=', record.employee_id.id),
                ('state', '=', 'approved')
            ])
            previous_salaries.write({'state': 'expired'})

    def action_cancelled(self):
        for record in self:
            if record.state != 'approved':
                raise ValidationError('Solo se puede cancelar un ajuste salarial en estado Aprobado.')
            record.state = 'cancelled'

    def unlink(self):
        for record in self:
            if record.state not in ['draft', 'cancelled']:
                raise ValidationError('No se puede eliminar un ajuste salarial que no esté en estado Borrador o Cancelado.')
        return super(HrEmployeeSalary, self).unlink()