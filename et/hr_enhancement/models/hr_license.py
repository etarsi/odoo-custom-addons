from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta

class hrLicense(models.Model):
    _name = 'hr.license'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    _description = 'Licencia del Empleado'

    description = fields.Text('Descripción', tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True, tracking=True)
    requested_date = fields.Datetime('Fecha solicitada', defaulta=lambda self: fields.Datetime.now())
    start_date = fields.Date('Fecha Inicio', required=True, tracking=True)
    end_date = fields.Date('Fecha Fin', store=True, readonly=False, tracking=True)
    days_qty = fields.Integer('Cantidad de días', default=0, compute='_compute_end_date', required=True, tracking=True, store=True)
    license_type_id = fields.Many2one('hr.license.type', string='Tipo de Licencia', domain="[('active', '=', True)]", required=True, tracking=True)
    reason = fields.Char('Motivo', tracking=True)
    state = fields.Selection(selection=[
        ('draft', 'Borrador'),
        ('pending', 'Pendiente de Aprobación'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], string='Estado', required=True, default='draft', tracking=True)
    approver_id = fields.Many2one('res.users', string="Aprobador")
    approver_date = fields.Datetime('Fecha de Aprobación')
    reject_id = fields.Many2one('res.users', string="Rechazador")
    reject_date = fields.Datetime('Fecha de Rechazo')
    document = fields.Binary('Documento de Licencia', required=True, tracking=True)
    document_name = fields.Char('Nombre del Documento', required=True, tracking=True)

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError('Solo se puede confirmar una licencia en estado Borrador.')
            record.state = 'pending'

    def action_approve(self):
        for record in self:
            if record.state != 'pending':
                raise ValidationError('Solo se puede aprobar una licencia en estado Pendiente.')
            record.state = 'approved'
            record.approver_id = self.env.user.id
            record.approver_date = fields.Datetime.now()

    def action_reject(self):
        for record in self:
            if record.state != 'pending':
                raise UserError('Solo se puede rechazar una licencia en estado Pendiente.')
            record.state = 'rejected'
            record.reject_id = self.env.user.id
            record.reject_date = fields.Datetime.now()
            
    @api.onchange('start_date', 'end_date')
    def _compute_end_date(self):
        for record in self:
            if record.start_date and record.days_qty:
                record.end_date = record.start_date + timedelta(days=record.days_qty)
            else:
                record.end_date = False