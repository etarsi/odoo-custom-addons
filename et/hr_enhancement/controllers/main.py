from odoo import http
from odoo.http import request, Response
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import pytz, traceback, json


def _get_param_float(key, default=None):
    """Lee paramétricas. Acepta '07:30' -> 7.5 o '7.5' -> 7.5."""
    raw = float(request.env['ir.config_parameter'].sudo().get_param(key) + 3) #
    if raw in (None, ''):
        return default
    s = str(raw).strip()
    try:
        if ':' in s:
            h, m = s.split(':', 1)
            return int(h) + int(m)/60.0
        return float(s)
    except Exception:
        return default

def _to_utc_naive(dt_local_aware):
    """Aware (con tz) -> naive UTC (lo que guarda Odoo)."""
    return dt_local_aware.astimezone(pytz.UTC).replace(tzinfo=None)

class HrAttendanceController(http.Controller):
    
    @http.route('/hr_enhancement/attendance', type='json', auth='public', csrf=False, methods=['POST'])
    def attendance_webhook(self, **kw):
        # Para ver lo que llega siempre
        data = request.jsonrequest or {}
        try:
            employee_dni = data.get('dni')
            employee_name = data.get('name')
            check_time = data.get('check_time')
            open_method = data.get('openMethod')

            if not (employee_dni and employee_name and check_time):
                return {'success': False, 'error': "Faltan 'dni', 'name' o 'check_time'.", 'received': data}

            # Soporta con o sin milisegundos
            fmt = "%Y-%m-%d %H:%M:%S.%f" if '.' in check_time else "%Y-%m-%d %H:%M:%S"
            try:
                check_local = datetime.strptime(check_time, fmt)   # datetime naive
            except Exception as pe:
                return {'success': False, 'error': f"Formato de 'check_time' inválido: {pe}", 'received': data}

            check_utc   = _to_utc_naive(check_local)                    # naive UTC (DB)
            # Paramétricas (seguras)
            p_day_start_limit   = _get_param_float('hr_enhancement.hour_start_day_check')
            p_day_end_limit     = _get_param_float('hr_enhancement.hour_end_day_check')
            p_night_start_limit = _get_param_float('hr_enhancement.hour_start_night_check')
            p_night_end_limit   = _get_param_float('hr_enhancement.hour_end_night_check')

            day = check_utc.date()
            start_limit_day = datetime.combine(day, p_day_start_limit)
            end_limit_day   = datetime.combine(day, p_day_end_limit)
            start_limit_night = datetime.combine(day, p_night_start_limit)
            end_limit_night   = datetime.combine(day, p_night_end_limit)
            hr_attendance = request.env['hr.attendance'].sudo()
            hr_employee = request.env['hr.employee'].sudo()
            employee = hr_employee.search([('dni', '=', employee_dni)], limit=1)
            message = f'Asistencia registrada para {employee_name} ({employee_dni}) a las {check_local.strftime("%Y-%m-%d %H:%M:%S")}'
            if open_method == 'FACE_RECOGNITION':
                if not employee:
                    employee = hr_employee.create({
                        'dni': employee_dni,
                        'name': employee_name,
                        'employee_type': 'employee',
                        'state': 'draft',
                    })
                    if check_utc > start_limit_day:
                        message += f'--asistencia fuera de rango diurno ({start_limit_day.strftime("%H:%M")}-{end_limit_day.strftime("%H:%M")})'
                    else:
                        open_att = hr_attendance.create({
                            'employee_id': employee.id,
                            'check_in': check_utc,  # naive UTC
                        })
                        message += f'--asistencia abierta: {open_att.id} (empleado en borrador)'
                else:
                    if check_utc > start_limit_day:
                        message += f'--asistencia fuera de rango diurno ({start_limit_day.strftime("%H:%M")}-{end_limit_day.strftime("%H:%M")})'
                    else:
                        open_att = hr_attendance.search([
                            ('employee_id', '=', employee.id),
                            ('check_in', '>=', check_utc - timedelta(minutes=5)),
                            ('check_out', '=', False),
                        ], limit=1)
                        if open_att:
                            open_att.write({'check_out': check_utc})
                            message += f' (asistencia cerrada: {open_att.id})'
                        else:
                            hr_attendance.create({
                                'employee_id': employee.id,
                                'check_in': check_utc,
                            })
                            message += ' (asistencia abierta)'
                return {'success': True, 'message': message}

            elif open_method == 'FINGERPRINT':
                if not employee:
                    employee = hr_employee.create({
                        'dni': employee_dni,
                        'name': employee_name,
                        'employee_type': 'eventual',
                        'state': 'active',
                    })
                    if check_utc > start_limit_day:
                        message += f'--asistencia fuera de rango diurno ({start_limit_day.strftime("%H:%M")}-{end_limit_day.strftime("%H:%M")})'
                    else:
                        open_att = hr_attendance.create({
                            'employee_id': employee.id,
                            'check_in': check_utc,  # naive UTC
                        })
                        message += f'--asistencia abierta: {open_att.id} (empleado en borrador)'
                else:
                    if employee.employee_type == 'eventual':
                        # Limites del día (para agrupar por día local)
                        open_att = hr_attendance.search([
                            ('employee_id', '=', employee.id),
                            ('check_in', '>=', check_utc),
                            ('check_in', '<=', check_utc),
                            ('check_out', '=', False)], limit=1)

                        if employee.type_shift == 'day':                            
                            if open_att:
                                if check_utc > end_limit_day:
                                    message += f'--asistencia fuera de rango diurno ({start_limit_day.strftime("%H:%M")}-{end_limit_day.strftime("%H:%M")})'
                                    return {'success': False, 'error': message, 'received': data}
                                # Cerrar asistencia abierta
                                open_att.write({'check_out': check_utc})
                                message += f' (asistencia cerrada: {open_att.id})'
                            else:
                                if check_utc > start_limit_day:
                                    message += f'--asistencia fuera de rango diurno ({start_limit_day.strftime("%H:%M")}-{end_limit_day.strftime("%H:%M")})'
                                    return {'success': False, 'error': message, 'received': data}
                                # Crear asistencia abierta
                                open_att = hr_attendance.create({
                                    'employee_id': employee.id,
                                    'check_in': check_utc,
                                })
                                message += f' (asistencia abierta: {open_att.id})'
                        elif employee.type_shift == 'night':
                            if open_att:
                                if check_utc > end_limit_night:
                                    message += f'--asistencia fuera de rango nocturno ({start_limit_night.strftime("%H:%M")}-{end_limit_night.strftime("%H:%M")})'
                                    return {'success': False, 'error': message, 'received': data}
                                # Cerrar asistencia abierta
                                open_att.write({'check_out': check_utc})
                                message += f' (asistencia cerrada: {open_att.id})'
                            else:
                                if check_utc > start_limit_night:
                                    message += f'--asistencia fuera de rango nocturno ({start_limit_night.strftime("%H:%M")}-{end_limit_night.strftime("%H:%M")})'
                                    return {'success': False, 'error': message, 'received': data}
                                # Crear asistencia abierta
                                open_att = hr_attendance.create({
                                    'employee_id': employee.id,
                                    'check_in': check_utc,
                                })
                                message += f' (asistencia abierta: {open_att.id})'
            return {'success': True, 'message': message}
        except ValidationError as ve:
            return {'success': False, 'error': str(ve), 'error_class': ve.__class__.__name__, 'received': data}
        except Exception as e:
            # rollback explícito por si quedó algo a medio camino
            request.env.cr.rollback()
            return {'success': False, 'error': str(e), 'received': data}
