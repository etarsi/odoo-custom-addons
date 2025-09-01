from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time
import pytz, math


def _float_to_time(f):
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

            check_utc = check_local + timedelta(hours=3)  # Convertir a UTC
            # Paramétricas (seguras)
            hr_enhancement = request.env['ir.config_parameter'].sudo()
            p_day_start_limit   = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_start_day_check')) + 3)
            p_day_end_limit     = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_end_day_check')) + 3)
            p_night_start_limit = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_start_night_check')) + 3)
            p_night_end_limit   = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_end_night_check')) + 3)

            day = check_utc.date()
            dow = day.weekday()
            start_limit_day = datetime.combine(day, p_day_start_limit)
            end_limit_day   = datetime.combine(day, p_day_end_limit)
            start_limit_night = datetime.combine(day, p_night_start_limit)
            end_limit_night   = datetime.combine(day, p_night_end_limit)
            hr_attendance = request.env['hr.attendance'].sudo()
            hr_employee = request.env['hr.employee'].sudo()
            employee = hr_employee.search([('id_lector', '=', employee_dni), ('state', '!=', 'inactive')], limit=1)
            message = f'ingreso: {check_utc.strftime("%Y-%m-%d %H:%M:%S")}--'
            if open_method == 'FACE_RECOGNITION':
                if not employee:
                    employee = hr_employee.create({
                        'id_lector': employee_dni,
                        'dni': employee_dni,
                        'name': employee_name,
                        'employee_type': 'employee',
                        'state': 'active',
                    })

            elif open_method == 'FINGERPRINT':
                if not employee:
                    employee = hr_employee.create({
                        'id_lector': employee_dni,
                        'dni': employee_dni,
                        'name': employee_name,
                        'employee_type': 'eventual',
                        'state': 'active',
                    })
                    if employee.type_shift == 'day':
                        if check_utc > start_limit_day:
                            # lo registro en el hr temp attendance
                            request.env['hr.temp.attendance'].sudo().create({
                                'employee_id': employee.id,
                                'check_date': check_utc,
                                'employee_type': employee.employee_type,
                            })
                            message += f'--asistencia fuera de rango diurno ({start_limit_day.strftime("%H:%M")}-{end_limit_day.strftime("%H:%M")})'
                            return {'success': False, 'error': message, 'received': data}
                        else:
                            open_att = hr_attendance.create({
                                'employee_id': employee.id,
                                'check_in': check_utc,  # naive UTC
                            })
                    elif employee.type_shift == 'night':
                        if check_utc > start_limit_night:
                            # lo registro en el hr temp attendance
                            request.env['hr.temp.attendance'].sudo().create({
                                'employee_id': employee.id,
                                'check_date': check_utc,
                                'employee_type': employee.employee_type,
                            })
                            message += f'--asistencia fuera de rango nocturno ({start_limit_night.strftime("%H:%M")}-{end_limit_night.strftime("%H:%M")})'
                            return {'success': False, 'error': message, 'received': data}
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
                            ('check_out', '=', False),
                            ('check_in', '<=', check_utc)], limit=1)
                        if employee.type_shift == 'day':
                            if open_att:
                                if dow in [0,1,2,3,4]:  # Lunes a Viernes
                                    if check_utc > end_limit_day:
                                        request.env['hr.temp.attendance'].sudo().create({
                                            'employee_id': employee.id,
                                            'check_date': check_utc,
                                            'employee_type': employee.employee_type,
                                        })
                                        message += f'--asistencia fuera del limite de salida diurno ({end_limit_day.strftime("%H:%M")})'
                                        return {'success': False, 'error': message, 'received': data}
                                # Cerrar asistencia abierta
                                open_att.write({'check_out': check_utc})
                                message += f' (asistencia cerrada: {open_att.id})'
                            else:
                                if dow in [0,1,2,3,4]:  # Lunes a Viernes
                                    if check_utc > start_limit_day:
                                        request.env['hr.temp.attendance'].sudo().create({
                                            'employee_id': employee.id,
                                            'check_date': check_utc,
                                            'employee_type': employee.employee_type,
                                        })
                                        message += f'--asistencia fuera del limite de ingreso diurno ({start_limit_day.strftime("%H:%M")})'
                                        return {'success': False, 'error': message, 'received': data}
                                elif dow == 5:  # Sábado
                                    p_day_start_limit   = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_start_day_check')) + 2)
                                    start_limit_day = datetime.combine(day, p_day_start_limit)
                                    if check_utc > start_limit_day:
                                        request.env['hr.temp.attendance'].sudo().create({
                                            'employee_id': employee.id,
                                            'check_date': check_utc,
                                            'employee_type': employee.employee_type,
                                        })
                                        message += f'--asistencia fuera del limite de ingreso diurno ({start_limit_day.strftime("%H:%M")})'
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
                                    request.env['hr.temp.attendance'].sudo().create({
                                        'employee_id': employee.id,
                                        'check_date': check_utc,
                                        'employee_type': employee.employee_type,
                                    })
                                    message += f'--asistencia fuera de rango nocturno ({end_limit_night.strftime("%H:%M")})'
                                    return {'success': False, 'error': message, 'received': data}
                                # Cerrar asistencia abierta
                                open_att.write({'check_out': check_utc})
                                message += f' (asistencia cerrada: {open_att.id})'
                            else:
                                if check_utc > start_limit_night:
                                    request.env['hr.temp.attendance'].sudo().create({
                                        'employee_id': employee.id,
                                        'check_date': check_utc,
                                        'employee_type': employee.employee_type,
                                    })
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