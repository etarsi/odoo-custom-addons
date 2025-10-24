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
    

    # ----------------- COMPUTES / CONSTRAINS -----------------
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
                raise ValidationError(_('La hora de finalización debe ser mayor a la de inicio.'))
            if r.total_hours <= 0:
                raise ValidationError(_('El total de horas debe ser mayor a 0.'))

    @api.constrains('justification')
    def _check_justification_words(self):
        for r in self:
            words = len((r.justification or '').strip().split())
            if words < 5:
                raise ValidationError(_('La justificación debe tener al menos 5 palabras.'))

    # ----------------- NOTIFICACIONES -----------------
    def _notify_hr_admins(self, subject, body_html):
        """Notifica a todos los usuarios del grupo HR Administrador."""
        try:
            group = self.env.ref('hr_enhancement.group_hr_administrador')
        except ValueError:
            group = False
        if not group:
            return
        partners = group.users.mapped('partner_id')
        if partners:
            self.message_post(
                subject=subject,
                body=body_html,
                partner_ids=partners.ids,
                subtype_xmlid='mail.mt_comment'
            )

    def _notify_employee(self, subject, body_html):
        """Notifica al empleado solicitante (si tiene usuario/partner)."""
        partner = self.user_id.partner_id if self.user_id else False
        if partner:
            self.message_post(
                subject=subject,
                body=body_html,
                partner_ids=[partner.id],
                subtype_xmlid='mail.mt_comment'
            )

    # ----------------- ACCIONES -----------------
    def action_submit(self):
        for r in self:
            if r.state != 'draft':
                raise ValidationError(_('Solo se puede enviar desde Borrador.'))
            r.state = 'submitted'
            # Notificar HR Admins
            subject = _("Nueva solicitud de horas extra")
            body = _(
                "<p>El empleado <b>%s</b> envió una solicitud de horas extra:</p>"
                "<ul>"
                "<li><b>Fecha:</b> %s (%s)</li>"
                "<li><b>Horario:</b> %.2f - %.2f (Total: %.1f h)</li>"
                "<li><b>Tarea:</b> %s</li>"
                "<li><b>Justificación:</b> %s</li>"
                "</ul>"
            ) % (
                r.employee_id.name or '',
                r.date or '',
                r.weekday or '',
                r.time_start or 0.0,
                r.time_end or 0.0,
                r.total_hours or 0.0,
                (r.task or '').replace('\n', '<br/>'),
                (r.justification or '').replace('\n', '<br/>'),
            )
            r._notify_hr_admins(subject, body)

    def action_approve(self):
        for r in self:
            if r.state != 'submitted':
                raise ValidationError(_('Solo se puede aprobar una solicitud enviada.'))
            r.write({'state': 'approved', 'approver_id': self.env.user.id, 'approval_date': fields.Datetime.now()})
            # Notificar empleado
            subject = _("Solicitud de horas extra aprobada")
            body = _(
                "<p>Tu solicitud de horas extra fue <b>aprobada</b>.</p>"
                "<ul>"
                "<li><b>Fecha:</b> %s (%s)</li>"
                "<li><b>Horario:</b> %.2f - %.2f (Total: %.1f h)</li>"
                "</ul>"
            ) % (r.date or '', r.weekday or '', r.time_start or 0.0, r.time_end or 0.0, r.total_hours or 0.0)
            r._notify_employee(subject, body)


    def action_reject(self):
        for r in self:
            if r.state != 'submitted':
                raise ValidationError(_('Solo se puede rechazar una solicitud enviada.'))
            r.state = 'rejected'
            # Notificar empleado
            subject = _("Solicitud de horas extra rechazada")
            body = _(
                "<p>Tu solicitud de horas extra fue <b>rechazada</b>.</p>"
                "<ul>"
                "<li><b>Fecha:</b> %s (%s)</li>"
                "<li><b>Horario:</b> %.2f - %.2f (Total: %.1f h)</li>"
                "</ul>"
            ) % (r.date or '', r.weekday or '', r.time_start or 0.0, r.time_end or 0.0, r.total_hours or 0.0)
            r._notify_employee(subject, body)

    @api.model
    def create(self, vals):
        if not vals.get('employee_id'):
            emp = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            if emp:
                vals['employee_id'] = emp.id
        return super().create(vals)