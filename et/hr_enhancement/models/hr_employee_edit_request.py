from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class HrEmployeeEditRequest(models.Model):
    _name = 'hr.employee.edit.request'
    _description = 'Solicitud de Edición de Empleado'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, ondelete='cascade')
    requested_by = fields.Many2one('res.users', string='Solicitado por', default=lambda self: self.env.user)
    request_date = fields.Datetime(string='Fecha Solicitud', default=fields.Datetime.now)
    approved_user_id = fields.Many2one('res.users', string='Aprobado por')
    approved_date = fields.Datetime('Fecha de aprobación')
    reason = fields.Text('Motivo de la Solicitud')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
    ], string='Estado', default='pending')
    
    @api.model
    def action_approve(self):
        for req in self:
            req.state = 'approved'
            req.approved_user_id = self.env.user
            req.approved_date = fields.Datetime.now()