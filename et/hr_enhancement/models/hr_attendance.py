from odoo import models, fields, api, exceptions, _
from datetime import time, datetime, timedelta
from odoo.exceptions import ValidationError, UserError
from odoo.tools import convert, format_duration, format_time, format_datetime
import math, re

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    overtime = fields.Float(
        string='Horas al 50%/Extra',
        compute="_compute_worked_hours",
        help="Horas extras del día (sin decimales, regla 30m -> 1h por tramo)."
    )
    # Ejemplo básico: horas trabajadas en feriado (ajustar a tu lógica)
    holiday_hours = fields.Float(
        string='Horas al 100%/Feriados/Sábados',
        compute="_compute_worked_hours",
        help="Horas trabajadas en feriados/Sábados después del medio día."
    )
    
    hours_late = fields.Float(
        string='Horas de retraso',
        store=True,
        compute="_compute_worked_hours",
        help='Horas de retraso contra la hora límite de entrada configurada.'
    )
    employee_type = fields.Selection(related='employee_id.employee_type', string='Tipo de Empleado', store=True)
    employee_type_shift = fields.Selection(related='employee_id.type_shift', string='Turno Asignado', store=True)
    blocked = fields.Boolean(string='Bloqueado', default=False)
    create_lector = fields.Boolean(string='Creado por Lector', default=False)
    justification = fields.Text(string='Justificación')
    day_of_week = fields.Selection(
        selection=[
            ('0', 'Lunes'),
            ('1', 'Martes'),
            ('2', 'Miércoles'),
            ('3', 'Jueves'),
            ('4', 'Viernes'),
            ('5', 'Sábado'),
            ('6', 'Domingo')
        ],
        string='Día Trabajado',
        store=True,
        compute='_compute_day_of_week'
    )

    @api.depends('check_in')
    def _compute_day_of_week(self):
        for rec in self:
            if rec.check_in:
                local_dt = fields.Datetime.context_timestamp(rec, rec.check_in)
                rec.day_of_week = str(local_dt.weekday())
            else:
                rec.day_of_week = False

    @api.constrains('justification')
    def _check_justification_min_words(self):
        for rec in self:
            if rec.create_lector:
                continue
            text = (rec.justification or '').strip()
            # cuenta palabras con letras/números (ignora dobles espacios y signos)
            words = re.findall(r'\w+', text, flags=re.UNICODE)
            if len(words) < 3:
                raise ValidationError(
                    f'La justificación debe tener al menos 3 palabras '
                    f'(actual: {len(words)}).'
                )

    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_worked_hours(self):
        for att in self:
            att.worked_hours = 0.0
            att.overtime = 0.0
            att.holiday_hours = 0.0
            att.hours_late = 0.0
            if att.check_in and att.check_out and att.employee_id:
                # Determinar tipo de empleado para elegir el schedule
                schedule = self.env['hr.work.schedule'].search([
                    ('type', '=', att.employee_id.employee_type),
                    ('state', '=', 'active')
                ], limit=1)
                if not schedule:
                    raise ValidationError("No se encontró un horario laboral activo para el empleado.")
                if att.employee_id.employee_type == 'eventual':
                    att.event_hours_employee_eventual(schedule)
                elif att.employee_id.employee_type == 'employee':
                    att.event_hours_employee(schedule)

    def event_hours_employee(self, schedule):
        for att in self:
            start_t = self._float_to_time(schedule.hour_start + 3)
            end_t   = self._float_to_time(schedule.hour_end + 3)
            day = att.check_in.date()
            start_dt = datetime.combine(day, start_t)
            end_dt   = datetime.combine(day, end_t)
            # REGLA SOLICITADA PARA check_in
            ci_floor = att.check_in.replace(minute=0, second=0, microsecond=0)
            eff_check_in = max(ci_floor, start_dt)
            eff_check_out = att.check_out
            #verificar si hay hr holiday custom
            holiday = self.env['hr.holiday.custom'].search([('date', '=', day)], limit=1)
            #sacar los dias
            dow = day.weekday()
            if dow == 6 or holiday:
                eff_check_in = att.check_in
                total_secs = max(0.0, (eff_check_out - eff_check_in).total_seconds())
                att.holiday_hours = float(self._round_30_up_to_int_hours(total_secs))
                att.worked_hours = 0.0
                att.overtime = 0.0
                att.hours_late = 0.0
                continue

            scheduled_overlap_secs = self._overlap_seconds(
                eff_check_in, eff_check_out, start_dt, end_dt
            )
            base_hours_raw = scheduled_overlap_secs / 3600.0

            if dow == 5:  # Sábado
                start_t = self._float_to_time(schedule.hour_start + 4) #comienzan 1 hora más tarde
                start_dt = datetime.combine(day, start_t)
                sat_end_t  = self._float_to_time(15.0) # terminan a las 12:00 BA
                sat_end_dt = datetime.combine(day, sat_end_t)
                base_secs_raw = self._overlap_seconds(
                    eff_check_in, eff_check_out, start_dt, sat_end_dt
                )
                base_hours_raw = base_secs_raw / 3600.0
                holiday_base = 0.0
                if eff_check_out > sat_end_dt:
                    holiday_base = max(0.0, (eff_check_out - max(eff_check_in, sat_end_dt)).total_seconds())
                att.holiday_hours += float(self._round_30_up_to_int_hours(holiday_base))
                att.worked_hours = base_hours_raw
                att.overtime = 0.0
            else:
                # ===== Lunes a Viernes (tu lógica original) =====
                base_hours = base_hours_raw
                over_time_base = 0.0
                if eff_check_out > end_dt:
                    over_time_base = max(0.0, (eff_check_out - max(eff_check_in, end_dt)).total_seconds())
                att.overtime += float(self._round_30_up_to_int_hours(over_time_base))
                att.worked_hours = base_hours

    def event_hours_employee_eventual(self, schedule):
        for att in self:
            # ======================== DÍA =========================
            if att.employee_id.type_shift == 'day':
                start_t = self._float_to_time(schedule.hour_start + 3)
                end_t   = self._float_to_time(schedule.hour_end + 3)
                day = att.check_in.date()
                start_dt = datetime.combine(day, start_t)
                end_dt   = datetime.combine(day, end_t)
                # REGLA SOLICITADA PARA check_in
                ci_floor = att.check_in.replace(minute=0, second=0, microsecond=0)
                eff_check_in = max(ci_floor, start_dt)
                eff_check_out = att.check_out
                #verificar si hay hr holiday custom
                holiday = self.env['hr.holiday.custom'].search([('date', '=', day)], limit=1)
                #sacar los dias
                dow = day.weekday()
                if dow == 6 or holiday:
                    eff_check_in = att.check_in
                    total_secs = max(0.0, (eff_check_out - eff_check_in).total_seconds())
                    att.holiday_hours = float(self._round_30_up_to_int_hours(total_secs))
                    att.worked_hours = 0.0
                    att.overtime = 0.0
                    att.hours_late = 0.0
                    continue

                if dow == 5:  # Sábado
                    start_t = self._float_to_time(schedule.hour_start + 4) #comienzan 1 hora más tarde
                    start_dt = datetime.combine(day, start_t)
                    sat_end_t  = self._float_to_time(15.0) # terminan a las 12:00 BA
                    sat_end_dt = datetime.combine(day, sat_end_t)
                    base_secs_raw = self._overlap_seconds(eff_check_in, eff_check_out, start_dt, sat_end_dt)
                    holiday_base = 0.0
                    if eff_check_out > sat_end_dt:
                        holiday_base = max(0.0, (eff_check_out - max(eff_check_in, sat_end_dt)).total_seconds())
                    att.holiday_hours += float(self._round_30_up_to_int_hours(holiday_base))
                    att.worked_hours += float(self._round_30_up_to_int_hours(base_secs_raw))
                    att.overtime = 0.0
                else:
                    # ===== Lunes a Viernes (tu lógica original) =====
                    scheduled_overlap_labor = self._overlap_seconds(eff_check_in, eff_check_out, start_dt, end_dt)
                    over_time_base = 0.0
                    if eff_check_out > end_dt:
                        over_time_base = max(0.0, (eff_check_out - max(eff_check_in, end_dt)).total_seconds())
                    att.overtime += float(self._round_30_up_to_int_hours(over_time_base))
                    att.worked_hours += float(self._round_30_up_to_int_hours(scheduled_overlap_labor))
            # ========================= NOCHE =========================
            elif att.employee_id.type_shift == 'night':
                start_t = self._float_to_time(schedule.hour_start_night + 3)
                end_t   = self._float_to_time(schedule.hour_end_night + 3)
                day = att.check_in.date()
                start_dt = datetime.combine(day, start_t)
                end_dt   = datetime.combine(day, end_t)

                if end_dt <= start_dt:
                    end_dt = end_dt + timedelta(days=1)
                # ========= REGLA SOLICITADA PARA check_in =========
                ci_floor = att.check_in.replace(minute=0, second=0, microsecond=0)
                eff_check_in = max(ci_floor, start_dt)
                eff_check_out = att.check_out
                base_secs = self._overlap_seconds(eff_check_in, eff_check_out, start_dt, end_dt)
                base_hours_int = float(self._round_30_up_to_int_hours(base_secs))
                overtime_secs = 0.0
                if eff_check_out and eff_check_out > end_dt:
                    overtime_secs = (eff_check_out - max(eff_check_in, end_dt)).total_seconds()
                overtime_int = float(self._round_30_up_to_int_hours(overtime_secs))
                att.worked_hours = base_hours_int
                att.overtime = overtime_int
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
        if a_start >= b_start:
            start = min(a_start, b_start)
        else:
            start = max(a_start, b_start)
        end = min(a_end, b_end)
        return max(0.0, (end - start).total_seconds())
    
    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        for attendance in self:
            # we take the latest attendance before our check_in time and check it doesn't overlap with ours
            last_attendance_before_check_in = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<=', attendance.check_in),
                ('id', '!=', attendance.id),
            ], order='check_in desc', limit=1)
            if last_attendance_before_check_in and last_attendance_before_check_in.check_out and last_attendance_before_check_in.check_out > attendance.check_in:
                raise exceptions.ValidationError(_("Cannot create new attendance record for %(empl_name)s, the employee was already checked in on %(datetime)s",
                                                   empl_name=attendance.employee_id.name,
                                                   datetime=format_datetime(self.env, attendance.check_in, dt_format=False)))

            if attendance.check_out:
                # we verify that the latest attendance with check_in time before our check_out time
                # is the same as the one before our check_in time computed before, otherwise it overlaps
                last_attendance_before_check_out = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_in', '<', attendance.check_out),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                if last_attendance_before_check_out and last_attendance_before_check_in != last_attendance_before_check_out:
                    raise exceptions.ValidationError(_("Cannot create new attendance record for %(empl_name)s, the employee was already checked in on %(datetime)s",
                                                       empl_name=attendance.employee_id.name,
                                                       datetime=format_datetime(self.env, last_attendance_before_check_out.check_in, dt_format=False)))
    
