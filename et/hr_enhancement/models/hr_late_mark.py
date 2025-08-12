# -*- coding: utf-8 -*-
from odoo import models, fields, api
import pytz
from datetime import datetime


class HrLateMark(models.Model):
    _name = 'hr.late.mark'
    _description = 'Marca fuera de horario (reporte interno)'
    _order = 'check_in desc'
    _rec_name = 'employee_id'

    employee_id   = fields.Many2one('hr.employee', string='Empleado', required=True, index=True)
    check_date    = fields.Datetime('Fecha/Hora de marca', required=True, index=True)
    limit_time_float   = fields.Float('Límite de entrada (h)', help='Ej: 7.25 = 07:15')
    open_method  = fields.Char('Método (dispositivo)', help='Ej: FINGERPRINT, FACE_RECOGNITION')
    notes        = fields.Text('Notas')

    
    @api.depends('check_in')
    def _compute_local_info(self):
        for rec in self:
            if not rec.check_in:
                rec.check_in_local = False
                rec.local_date = False
                continue
            # check_in está en UTC naive -> aware UTC -> BA
            aware_utc = rec.check_in.replace(tzinfo=pytz.UTC)
            local_dt  = aware_utc.astimezone(BA_TZ)
            rec.check_in_local = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            rec.local_date = local_dt.date()

    @api.model
    def log_late(self, employee, check_in_utc, limit_float, open_method=None, attendance=None, source_device=None, notes=None):
        """Helper para crear el registro de marca tardía."""
        # calcular hora local float y minutos de retraso
        aware_utc = check_in_utc.replace(tzinfo=pytz.UTC)
        local_dt  = aware_utc.astimezone(BA_TZ)
        hh = local_dt.hour + local_dt.minute/60.0 + local_dt.second/3600.0

        late_minutes = 0
        if isinstance(limit_float, (int, float)):
            lm = max(0.0, (hh - float(limit_float)) * 60.0)
            late_minutes = int(round(lm))

        vals = {
            'employee_id': employee.id,
            'attendance_id': attendance.id if attendance else False,
            'check_in': check_in_utc,
            'limit_time_float': float(limit_float) if limit_float is not None else False,
            'marked_hour_float': round(hh, 4),
            'late_minutes': late_minutes,
            'open_method': open_method or '',
            'source_device': source_device or '',
            'notes': notes or '',
        }
        return self.create(vals)
