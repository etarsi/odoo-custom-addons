# models/hr_overtime.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError

WEEKDAY_ES = {
    0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves',
    4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
}

def round_half_hour(hours):
    # Redondea a múltiplos de 0.5 h
    return round(hours * 2) / 2.0

class HrOvertimeRequest(models.Model):
    _name = 'hr.overtime.request'
    _description = 'Solicitud de Horas Extra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)
    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True, tracking=True, default=lambda self: self.env.user.employee_id, domain="[('employee_type', '!=', 'eventual')]")
    user_id = fields.Many2one(related='employee_id.user_id', store=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True, string='Área')
    date = fields.Date('Fecha', required=True, default=fields.Date.context_today, tracking=True)
    weekday = fields.Char('Día', compute='_compute_weekday', store=True, readonly=True)
    task = fields.Text('Tarea/Proyecto')
    justification = fields.Text('Justificación (especificar motivo)', required=True)
    time_start = fields.Float('Hora de inicio', required=True, help='Formato 24h: 18.5 = 18:30')
    time_end   = fields.Float('Hora de finalización', required=True)
    total_hours = fields.Float('Total de horas', compute='_compute_total', store=True, readonly=True)
    approver_id = fields.Many2one('res.users', 'Aprobador', readonly=True)
    approval_date = fields.Datetime('Fecha de aprobación', readonly=True)
    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('submitted', 'Enviado'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], default='draft', tracking=True, string='Estado')
    

    @api.depends('date')
    def _compute_weekday(self):
        for r in self:
            r.weekday = WEEKDAY_ES[fields.Date.from_string(r.date).weekday()] if r.date else False

    @api.depends('time_start', 'time_end')
    def _compute_total(self):
        for r in self:
            hours = max(0.0, (r.time_end or 0.0) - (r.time_start or 0.0))
            r.total_hours = round_half_hour(hours)

    @api.constrains('time_start', 'time_end')
    def _check_times(self):
        for r in self:
            if r.time_end <= r.time_start:
                raise ValidationError('La hora de finalización debe ser mayor a la de inicio.')
            if r.total_hours <= 0:
                raise ValidationError('El total de horas debe ser mayor a 0.')

    @api.constrains('justification')
    def _check_justification_words(self):
        for r in self:
            words = len((r.justification or '').strip().split())
            if words < 5:
                raise ValidationError('La justificación debe tener al menos 5 palabras.')

    def action_submit(self):
        for r in self:
            if r.state != 'draft':
                raise ValidationError('Solo se puede enviar desde Borrador.')
            r.state = 'submitted'

    def action_approve(self):
        for r in self:
            if r.state != 'submitted':
                raise ValidationError('Solo se puede aprobar una solicitud enviada.')
            r.write({'state': 'approved', 'approver_id': self.env.user.id, 'approval_date': fields.Datetime.now()})

    def action_reject(self):
        for r in self:
            if r.state != 'submitted':
                raise ValidationError('Solo se puede rechazar una solicitud enviada.')
            r.state = 'rejected'

    @api.model
    def create(self, vals):
        if not vals.get('employee_id'):
            emp = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            if emp:
                vals['employee_id'] = emp.id
        return super().create(vals)