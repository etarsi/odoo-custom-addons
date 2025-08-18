# models/hr_employee_offboard.py
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class HrEmployeeOffboard(models.Model):
    _name = 'hr.employee.offboard'
    _description = 'Registro de Bajas de Empleados'
    _order = 'date desc, id desc'

    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True, ondelete='restrict', tracking=True)
    user_id = fields.Many2one('res.users', string="Dado de baja por", default=lambda s: s.env.user, readonly=True, tracking=True)
    date = fields.Date(string="Fecha de baja", required=True, default=fields.Date.context_today, tracking=True)
    reason = fields.Selection([
        ('resignation', 'Renuncia'),
        ('termination', 'Despido'),
        ('end_contract', 'Fin de contrato'),
        ('mutual', 'Acuerdo mutuo'),
        ('retirement', 'Jubilación'),
        ('other', 'Otro'),
    ], string="Motivo", required=True, tracking=True)
    description = fields.Text(string="Descripción / Observaciones")
    state = fields.Selection([('done', 'Registrado')], default='done', string="Estado", tracking=True)
