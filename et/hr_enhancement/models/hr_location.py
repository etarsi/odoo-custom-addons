from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class HrLocation(models.Model):
    _name = 'hr.location'
    _description = 'Ubicación del Empleado'
    _rec_name = 'street'

    street = fields.Char(string='Calle', required=True)
    street2 = fields.Char(string='Calle 2')
    city = fields.Char(string='Ciudad', required=True)
    floor = fields.Char(string='Piso')
    cp_code = fields.Char(string='Código Postal', required=True)
    country_id = fields.Many2one('res.country', string='País', required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, ondelete='cascade')
    latitude = fields.Float(string='Latitud')
    longitude = fields.Float(string='Longitud')
    state = fields.Selection(selection=[
        ('draft', 'Borrador'),
        ('pending', 'Pendiente de Aprobación'),
        ('approved', 'Aprobado')], string='Estado', required=True, default='draft')
    document = fields.Binary(string='Documento de Ubicación')
    document_name = fields.Char(string='Nombre del Documento')
    approver_id = fields.Many2one('res.users', string="Aprobador")
    approver_date = fields.Datetime('Fecha de Aprobación')
    
    _sql_constraints = [
        ('employee_unique', 'UNIQUE(employee_id)', 'Cada empleado solo puede tener una ubicación registrada.')
    ]

    @api.constrains('document', 'document_name')
    def _check_document(self):
        for record in self:
            if not record.document:
                raise ValidationError(_('El documento es obligatorio.'))
            if not record.document_name:
                raise ValidationError(_('El nombre del documento es obligatorio.'))
            if not record.document_name.lower().endswith(('.pdf')):
                raise ValidationError('Solo se pueden subir archivos PDF.')

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError('Solo se puede confirmar una licencia en estado Borrador.')
            record.state = 'pending'

    def action_approve(self):
        for record in self:
            if record.state != 'pending':
                raise UserError('Solo se puede aprobar una licencia en estado Pendiente.')
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