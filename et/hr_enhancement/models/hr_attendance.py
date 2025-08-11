from odoo import models, fields, api
from datetime import time, datetime, timedelta
from odoo.exceptions import ValidationError, UserError
import math

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Overtime sin decimales, se calcula en _compute_worked_hours
    overtime = fields.Float(
        string='Horas Extra',
        compute="_compute_worked_hours",
        help="Horas extras del día (sin decimales, regla 30m -> 1h por tramo)."
    )
    # Ejemplo básico: horas trabajadas en feriado (ajustar a tu lógica)
    holiday_hours = fields.Float(
        string='Horas Feriado',
        compute="_compute_holiday_hours",
        help="Horas trabajadas en feriado."
    )

    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_worked_hours(self):
        """
        worked_hours = horas dentro del horario (start-end) - break (si check_out > break_start)
                       + overtime_before (redondeo 30m -> 1h, entero)
                       + overtime_after  (redondeo 30m -> 1h, entero)
                       + holiday_hours

        Reglas pedidas:
        - El break se descuenta SOLO si check_out > inicio del break, y solo el solapamiento real.
        - Overtime sin decimales, redondeo por tramo (antes y después):
            >=30min => +1h, <30min => 0h. El redondeo se aplica POR TRAMO, y luego se suman.
        """
        for att in self:
            att.worked_hours = 0.0
            att.overtime = 0.0
            att.holiday_hours = 0.0
            if att.check_in and att.check_out and att.employee_id:
                # Determinar tipo de empleado para elegir el schedule
                type_employee = 'employee' if att.employee_id.employee_type == 'employee' else 'eventual'

                schedule = self.env['hr.work.schedule'].search([
                    ('type', '=', type_employee),
                    ('state', '=', 'active')
                ], limit=1)
                if not schedule:
                    raise UserError("No se encontró un horario laboral activo para el empleado.")

                # Si no es turno diurno, podés ajustar la lógica acá.
                if getattr(att.employee_id, 'type_shift', 'day') != 'day':
                    total_secs = (att.check_out - att.check_in).total_seconds()
                    att.overtime = float(self._round_30_up_to_int_hours(total_secs))
                    att.worked_hours = att.overtime + (att.holiday_hours or 0.0)
                    continue

                # ----- Horario programado (float -> time -> datetime del día) -----
                start_t = self._float_to_time(schedule.hour_start + 3)
                end_t   = self._float_to_time(schedule.hour_end + 3)

                day = att.check_in.date()
                start_dt = datetime.combine(day, start_t)
                end_dt   = datetime.combine(day, end_t)

                att_in  = att.check_in
                att_out = att.check_out

                # Solapamiento con el horario programado (en segundos)
                scheduled_overlap_secs = self._overlap_seconds(att_in, att_out, start_dt, end_dt)

                b_start_t = self._float_to_time(schedule.break_start + 3)
                b_end_t   = self._float_to_time(schedule.break_end + 3)

                b_start_dt = datetime.combine(day, b_start_t)
                b_end_dt   = datetime.combine(day, b_end_t)

                # Descontar break SOLO si check_out > inicio del break, y solo el solapamiento real
                break_secs = 0.0
                if att_out > b_start_dt:
                    break_secs = self._overlap_seconds(att_in, att_out, b_start_dt, b_end_dt)

                # Horas base dentro del horario, menos break (nunca negativo)
                base_secs = max(0.0, scheduled_overlap_secs - break_secs)
                base_hours = base_secs / 3600.0

                over_time_base = 0.0
                if att_out > end_dt:
                    over_time_base = max(0.0, (att_out - max(att_in, end_dt)).total_seconds())
                # Redondeo por tramo: >=30 min -> 1h; <30 -> 0h (sin decimales)
                overtime_time_base_hours = float(self._round_30_up_to_int_hours(over_time_base))

                # Resultado final
                att.overtime = overtime_time_base_hours
                att.worked_hours = base_hours
                
    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        return True

    @api.depends('check_in', 'check_out')
    def _compute_holiday_hours(self):
        """
        Ejemplo simple: si la fecha de check_in está en feriados públicos,
        holiday_hours = horas totales trabajadas ese día; de lo contrario 0.
        Ajustá la búsqueda según tu fuente de feriados (modelo/tabla que uses).
        """
        for att in self:
            att.holiday_hours = 0.0

    # ===================== VALIDACIONES =====================

    @api.constrains('overtime', 'holiday_hours')
    def _check_non_negative_hours(self):
        for att in self:
            if (att.overtime or 0.0) < 0 or (att.holiday_hours or 0.0) < 0:
                raise ValidationError("Las horas extra y las horas de feriado no pueden ser negativas.")

    # ===================== HELPERS =====================

    def _float_to_time(self, f):
        """Convierte 7.5 -> 07:30, 17.0 -> 17:00 (float a time)."""
        if f is None:
            return time(0, 0, 0)
        h = int(math.floor(f))
        m = int(round((f - h) * 60))
        if m == 60:  # por si entra 7.99999
            h += 1
            m = 0
        h = max(0, min(23, h))
        m = max(0, min(59, m))
        return time(h, m, 0)

    def _round_30_up_to_int_hours(self, seconds):
        """
        Redondeo entero por tramo:
        - <30 min -> 0h
        - >=30 min -> +1h
        - 1h20 -> 1h; 1h31 -> 2h; etc.
        """
        minutes = max(0.0, seconds) / 60.0
        return int((minutes + 30) // 60)

    def _overlap_seconds(self, a_start, a_end, b_start, b_end):
        """Segundos de solapamiento entre [a_start,a_end] y [b_start,b_end]."""
        start = max(a_start, b_start)
        end = min(a_end, b_end)
        return max(0.0, (end - start).total_seconds())
