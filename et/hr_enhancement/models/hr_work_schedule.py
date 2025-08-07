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
            for field_name in ['hour_start', 'hour_end', 'hour_start_night', 'hour_end_night']:
                value = getattr(rec, field_name)
                if value is not False:  # None or 0 is valid
                    if value < 0 or value >= 24:
                        raise ValidationError("La hora en '%s' debe estar entre 00:00 y 23:59." % dict(self._fields[field_name].string))
