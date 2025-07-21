from odoo import models, fields, api

class hrLicense(models.Model):
    _name = 'hr.license'

    employee_id = fields.Many2one('hr.employee', required=True)
    requested_date = fields.Datetime('Fecha solicitada', required=True)
    license_date = fields.Date('Fecha de licencia', required=True)
    days_qty = fields.Integer('Cantidad de días', default=0, required=True)
    license_data_fin = fields.Date('Fecha de fin de licencia')
    license_type_id = fields.Many2one('hr.license.type', string='Tipo de Licencia', required=True)
    reason = fields.Char('Motivo', required=True)
    state = fields.Selection(selection=[
        ('draft', 'Borrador'),
        ('pending', 'Pendiente de Aprobación'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], string='Estado', required=True)
    approver_id = fields.Many2one('res.users', string="Aprobador")
    approver_date = fields.Datetime('Fecha de Aprobación')
    

    @api.model
    def create(self, vals):
        employee = self.env['hr.employee'].browse(vals.get('employee'))
        if employee.parent_id and employee.parent_id.user_id:
            vals['approver'] = employee.parent_id.user_id.id
        return super().create(vals)

    def confirm(self):
        self.state = 'pending'

    def approve(self):
        self.state = 'approved'

    def reject(self):
        self.state = 'rejected'

    def cancel(self):
        self.state = 'draft'