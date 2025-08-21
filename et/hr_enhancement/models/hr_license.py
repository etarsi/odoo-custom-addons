from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta

class hrLicense(models.Model):
    _name = 'hr.license'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    _description = 'Licencia del Empleado'

    description = fields.Text('Descripción', tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True, tracking=True)
    requested_date = fields.Datetime('Fecha solicitada', default=lambda self: fields.Datetime.now())
    start_date = fields.Date('Fecha Inicio', required=True, default=fields.Date.today, tracking=True)
    end_date = fields.Date('Fecha Fin', store=True, default=fields.Date.today, tracking=True)
    days_qty = fields.Integer('Cantidad de días', default=0, compute='_compute_days_qty', required=True, readonly=True, tracking=True, store=True)
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
    
    #CAMPOS PARA UNA LICENCIA DE TIPO LICENCIA POR ART
    art_case_number = fields.Char('N° Siniestro ART')
    art_type = fields.Selection([
        ('work', 'Accidente de trabajo'),
        ('initinere', 'Accidente in itinere'),
        ('prof_disease', 'Enfermedad profesional'),
    ], string='Tipo de Siniestro')
    art_date = fields.Date('Fecha del Siniestro')
    art_diagnosis = fields.Char('Diagnóstico Médico')
    alta_afip = fields.Date('Fecha de Alta Médica/AFIP')
    art_company = fields.Char('Nombre de la ART')
    
    

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        # Buscar el empleado del usuario actual
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if employee:
            res['employee_id'] = employee.id
        return res

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
    def _compute_days_qty(self):
        for record in self:
            if record.start_date and record.end_date:
                if record.start_date > record.end_date:
                    raise ValidationError("La Fecha de Inicio no debe ser mayor a la Fecha Final de la Licencia.")
                # Si quieres ambos días INCLUSIVOS (ej: 2024-06-01 a 2024-06-03 = 3 días)
                delta = (record.end_date - record.start_date).days + 1
                record.days_qty = delta if delta > 0 else 0
            else:
                record.days_qty = 0
                