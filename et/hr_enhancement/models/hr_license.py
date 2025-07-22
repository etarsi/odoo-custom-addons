from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class hrLicense(models.Model):
    _name = 'hr.license'

    employee_id = fields.Many2one('hr.employee', required=True)
    requested_date = fields.Datetime('Fecha solicitada', required=True)
    license_date = fields.Date('Fecha de licencia', required=True)
    days_qty = fields.Integer('Cantidad de días', default=0, required=True)
    license_data_fin = fields.Date('Fecha de fin de licencia')
    license_type_id = fields.Many2one('hr.license.type', string='Tipo de Licencia', domain="[('active', '=', True)]", required=True)
    reason = fields.Char('Motivo', required=True)
    state = fields.Selection(selection=[
        ('draft', 'Borrador'),
        ('pending', 'Pendiente de Aprobación'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], string='Estado', required=True, default='draft')
    approver_id = fields.Many2one('res.users', string="Aprobador")
    approver_date = fields.Datetime('Fecha de Aprobación')
    reject_id = fields.Many2one('res.users', string="Rechazador")
    reject_date = fields.Datetime('Fecha de Rechazo')
    

    @api.model
    def create(self, vals):
        employee = self.env['hr.employee'].browse(vals.get('employee'))
        if employee.parent_id and employee.parent_id.user_id:
            vals['approver'] = employee.parent_id.user_id.id
        return super().create(vals)
    
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