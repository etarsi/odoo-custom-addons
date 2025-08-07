# hr_enhancement/models/hr_work_schedule.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrWorkSchedule(models.Model):
    _name = 'hr.work.schedule'
    _description = 'Rango de Horario Laboral'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    type = fields.Selection([
        ('empleado', 'Empleado'),
        ('eventual', 'Eventual')
    ], string="Tipo", default="empleado", required=True, tracking=True)
    hour_start = fields.Float(string="Hora Inicio (Normal)", required=True, tracking=True)
    hour_end = fields.Float(string="Hora Fin (Normal)", required=True, tracking=True)
    hour_start_night = fields.Float(string="Hora Inicio (Noche)", tracking=True)
    hour_end_night = fields.Float(string="Hora Fin (Noche)", tracking=True)
    state = fields.Selection([
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo')
    ], string="Estado", default="inactivo", required=True, tracking=True)

    _sql_constraints = [
        ('unique_tipo_activo', 'unique(tipo, state)', 'Sólo puede haber un horario ACTIVO por tipo.'),
    ]