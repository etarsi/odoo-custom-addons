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
        """
        for att in self:
            att.worked_hours = 0.0
            att.overtime = 0.0
            att.holiday_hours = att.holiday_hours or 0.0

            if not (att.check_in and att.check_out and att.employee_id):
                continue
            if att.check_out <= att.check_in:
                continue

            # --- Convertir a HORA LOCAL para comparar con floats locales del schedule ---
            local_in = fields.Datetime.context_timestamp(att, att.check_in)
            local_out = fields.Datetime.context_timestamp(att, att.check_out)

            # Tipo de empleado para elegir schedule
            type_employee = 'employee' if getattr(att.employee_id, 'employee_type', 'employee') == 'employee' else 'eventual'
            schedule = self.env['hr.work.schedule'].search([
                ('type', '=', type_employee),
                ('state', '=', 'active')
            ], limit=1)
            if not schedule:
                raise UserError("No se encontró un horario laboral activo para el empleado.")

            # Si no es turno diurno, considerar todas las horas como extra (ajustá si tenés otra lógica)
            if getattr(att.employee_id, 'type_shift', 'day') != 'day':
                total_secs = (local_out - local_in).total_seconds()
                att.overtime = float(self._round_30_up_to_int_hours(total_secs))
                att.worked_hours = att.overtime + (att.holiday_hours or 0.0)
                continue

            # ----- Horario programado (float -> time -> datetime local del día) -----
            start_t = self._float_to_time(schedule.hour_start)
            end_t   = self._float_to_time(schedule.hour_end)
            day = local_in.date()
            start_dt = datetime.combine(day, start_t)
            end_dt   = datetime.combine(day, end_t)

            # Solapamiento con horario (en segundos, local)
            scheduled_overlap_secs = self._overlap_seconds(local_in, local_out, start_dt, end_dt)

            # ----- Break (por defecto 13:00–14:00 si no está definido) -----
            b_start_f = getattr(schedule, 'break_start', 13.0)
            b_end_f   = getattr(schedule,  'break_end',   14.0)
            b_start_dt = datetime.combine(day, self._float_to_time(b_start_f))
            b_end_dt   = datetime.combine(day, self._float_to_time(b_end_f))

            # Descontar break SOLO si check_out > inicio del break, y solo el solapamiento real
            break_secs = 0.0
            if local_out > b_start_dt:
                break_secs = self._overlap_seconds(local_in, local_out, b_start_dt, b_end_dt)

            # Horas base dentro del horario, menos break (nunca negativo)
            base_secs = max(0.0, scheduled_overlap_secs - break_secs)
            base_hours = base_secs / 3600.0

            # ----- OVERTIME por tramo (antes y después), redondeo 30m -> 1h, sin decimales -----
            overtime_before_secs = 0.0
            #if local_in < start_dt:
            #    overtime_before_secs = max(0.0, (min(local_out, start_dt) - local_in).total_seconds())

            overtime_after_secs = 0.0
            if local_out > end_dt:
                overtime_after_secs = max(0.0, (local_out - max(local_in, end_dt)).total_seconds())

            overtime_before_hours = float(self._round_30_up_to_int_hours(overtime_before_secs))
            overtime_after_hours  = float(self._round_30_up_to_int_hours(overtime_after_secs))
            overtime_hours = overtime_before_hours + overtime_after_hours

            # Resultado final
            att.overtime = overtime_hours
            att.worked_hours = base_hours + overtime_hours + (att.holiday_hours or 0.0)

                
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
