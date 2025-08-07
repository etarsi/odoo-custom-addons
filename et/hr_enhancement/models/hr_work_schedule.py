# hr_enhancement/models/hr_work_schedule.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrWorkSchedule(models.Model):
    _name = 'hr.work.schedule'
    _description = 'Rango de Horario Laboral'

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

    @api.constrains('hour_start', 'hour_end', 'hour_start_night', 'hour_end_night')
    def _check_hours(self):
        for rec in self:
            if rec.hour_start < 0 or rec.hour_end < 0 or rec.hour_start_night < 0 or rec.hour_end_night < 0:
                raise ValidationError("Las horas no pueden ser negativas.")
            if rec.hour_start >= rec.hour_end:
                raise ValidationError("La hora de inicio debe ser menor que la hora de fin.")
            if rec.hour_start_night and rec.hour_end_night and rec.hour_start_night >= rec.hour_end_night:
                raise ValidationError("La hora de inicio (noche) debe ser menor que la hora de fin (noche).")
