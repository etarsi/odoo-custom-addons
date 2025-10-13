from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter
from . import excel

MESES_ES = {
    '01': 'Enero',
    '02': 'Febrero',
    '03': 'Marzo',
    '04': 'Abril',
    '05': 'Mayo',
    '06': 'Junio',
    '07': 'Julio',
    '08': 'Agosto',
    '09': 'Septiembre',
    '10': 'Octubre',
    '11': 'Noviembre',
    '12': 'Diciembre',
}

class HrReportAttendanceWizard(models.TransientModel):
    _name = 'hr.report.attendance.wizard'
    _description = 'Wizard para Exportar Asistencias a Excel'

    date_start = fields.Date('Fecha inicio', required=True, default=fields.Date.context_today)
    date_end = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados',
    )
    employee_type = fields.Selection(
        string='Tipo de Empleado',
        selection=[('employee', 'Empleado'), ('eventual', 'Eventual'), ('all', 'Todos')], default='all'
    )
    employee_type_shift = fields.Selection(
        string='Turno Asignado',
        selection=[('day', 'Día'), ('night', 'Noche'), ('all', 'Todos')], default='all'
    )
    
    def action_generar_excel(self):
        return True