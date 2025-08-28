from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date


class HrTempAttendance(models.Model):
    _name = 'hr.temp.attendance'
    _description = 'Temporary Attendance'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    check_date = fields.Datetime(string='Check Fecha', required=True)
    employee_type = fields.Selection(related='employee_id.employee_type', string='Tipo de Empleado', store=True)
    
