from odoo import models, fields, api
from datetime import time, datetime, timedelta
from odoo.exceptions import ValidationError, UserError
import math

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    overtime = fields.Float(string='Horas Extra', compute="_compute_overtime", help="Horas extras del día.")
    holiday_hours = fields.Float(string='Horas Feriado', compute="_compute_holiday_hours", help="Horas trabajadas en feriado.")

    # IMPORTANTE: incluimos los nuevos campos en el depends del compute
    @api.depends('check_in', 'check_out', 'overtime', 'holiday_hours')
    def _compute_worked_hours(self):
        """
        Recalcula worked_hours sumando:
        - horas base (check_out - check_in)
        - + overtime
        - + holiday_hours
        """
        for att in self:
            base = 0.0
            if att.check_in and att.check_out and att.employee_id:
                if att.employee_id.employee_type == 'employee':
                    type_employee = 'employee'
                else:
                    type_employee = 'eventual'
                schedule = self.env['hr.work.schedule'].search([('type', '=', type_employee), ('state', '=', 'active')], limit=1)
                if not schedule:
                    raise UserError("No se encontró un horario laboral activo para el empleado.")
                if att.employee_id.type_shift == 'day':
                    start_t = self._float_to_time(schedule.hour_start)   # ej 07:00
                    end_t   = self._float_to_time(schedule.hour_end)     # ej 17:00
                    bstart_t= self._float_to_time(schedule.break_start)     # ej 13.0 => 13:00
                    bend_t  = self._float_to_time(schedule.break_end)       # ej 14.0 => 14:00
                    # Usar TZ contextual
                    tz_name = att.employee_id.tz or self.env.user.tz or 'UTC'
                    check_in_local = fields.Datetime.context_timestamp(att.with_context(tz=tz_name), att.check_in)
                    check_out_local = fields.Datetime.context_timestamp(att.with_context(tz=tz_name), att.check_out)
                    # Calcular horas trabajadas
                    base = self._overlap_seconds(check_in_local, check_out_local, start_t, end_t) / 3600.0

    @api.constrains('overtime', 'holiday_hours')
    def _check_non_negative_hours(self):
        for att in self:
            if (att.overtime or 0.0) < 0 or (att.holiday_hours or 0.0) < 0:
                raise ValidationError("Las horas extra y las horas de feriado no pueden ser negativas.")

    def _round_30_up_to_int_hours(self, seconds):
        """Regla: >=30 min suma 1 hora, sin decimales."""
        minutes = max(0.0, seconds) / 60.0
        return int((minutes + 30) // 60)
    
    # Helpers
    def _float_to_time(self, f):
        """Convierte 7.5 -> 07:30, 17.0 -> 17:00 (float a time)."""
        if f is None:
            return None
        h = int(math.floor(f))
        m = int(round((f - h) * 60))
        if m == 60:  # por si entra 7.99999
            h += 1
            m = 0
        h = max(0, min(23, h))
        m = max(0, min(59, m))
        return time(h, m, 0)

    def _round_30_to_int_hours(self, seconds):
        """Regla: >= 30 minutos suma 1h. Sin decimales."""
        minutes = max(0.0, seconds) / 60.0
        return int((minutes + 30) // 60)

    def _overlap_seconds(self, a_start, a_end, b_start, b_end):
        start = max(a_start, b_start)
        end = min(a_end, b_end)
        return max(0.0, (end - start).total_seconds())