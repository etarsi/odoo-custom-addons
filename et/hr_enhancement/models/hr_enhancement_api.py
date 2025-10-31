from odoo import http, api, SUPERUSER_ID, models, re
from odoo.http import request
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time
import pytz, math, odoo


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

def _get_json():
    data = request.jsonrequest or {}
    if isinstance(data, dict) and 'params' in data and isinstance(data['params'], dict):
        data = data['params']
    return data

def _parse_shift_from_dni(dni: str):
    s = (dni or '').strip()
    if not s:
        return '', 'day'
    if s[0] in ('N', 'n'):
        core = s[1:].strip()
        return core, 'night'
    return s, 'day'

class HrEnhancementApi(models.AbstractModel):
    _name = 'hr.enhancement.api'
    _description = 'API hr_enhancement sin http.route'
    
    @api.model
    def attendance_webhook(self, data):
        # Para ver lo que llega siempre
        reg = odoo.registry('one')
        env = self.env
        with reg.cursor() as cr:
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
                hr_enhancement = env['ir.config_parameter'].sudo()
                p_day_start_limit   = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_start_day_check')) + 3)
                p_day_end_limit     = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_end_day_check')) + 3)
                p_night_start_limit = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_start_night_check')) + 3)
                p_night_end_limit   = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_end_night_check')) + 3)
                
                p_day_start_limit_inicio_marcado = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_start_day_check')) + 1)
                p_night_start_limit_inicio_marcado = _float_to_time(float(hr_enhancement.get_param('hr_enhancement.hour_start_night_check')) + 1)

                day = check_utc.date()
                dow = day.weekday()
                start_limit_day = datetime.combine(day, p_day_start_limit)
                end_limit_day   = datetime.combine(day, p_day_end_limit)
                start_limit_night = datetime.combine(day, p_night_start_limit)
                end_limit_night   = datetime.combine(day, p_night_end_limit)
                start_limit_day_inicio_marcado = datetime.combine(day, p_day_start_limit_inicio_marcado)
                start_limit_night_inicio_marcado = datetime.combine(day, p_night_start_limit_inicio_marcado)
                hr_attendance = env['hr.attendance'].sudo()
                hr_employee = env['hr.employee'].sudo()
                employee = hr_employee.search([('id_lector', '=', employee_dni), ('state', '!=', 'inactive')], limit=1)
                message = f'ingreso: {check_utc.strftime("%Y-%m-%d %H:%M:%S")}--'
                dni, type_shift = _parse_shift_from_dni(employee_dni)
                if open_method == 'FACE_RECOGNITION':
                    if not employee:
                        employee = hr_employee.create({
                            'id_lector': employee_dni,
                            'dni': employee_dni,
                            'name': employee_name,
                            'employee_type': 'employee',
                            'state': 'active',
                            'work_schedule_id': env['hr.work.schedule'].search([('type', '=', 'employee'), ('state', '=', 'active')], limit=1).id,
                        })
                        if check_utc > start_limit_day_inicio_marcado:
                            open_att = hr_attendance.create({
                                'employee_id': employee.id,
                                'check_in': check_utc,  # naive UT
                                'create_lector': True,
                            })
                        else:
                            message += '--asistencia fuera del rango diurno de inicio de marcado'
                            return {'success': False, 'error': message, 'received': data}
                        message += f'--asistencia abierta: {open_att.id} (empleado en borrador)'
                    else:
                        # Limites del día (para agrupar por día local)
                        open_att = hr_attendance.search([
                            ('employee_id', '=', employee.id),
                            ('check_out', '=', False),
                            ('blocked', '=', False)], limit=1, order='check_in desc')
                        if open_att:
                            if open_att.check_in.date() == check_utc.date():
                                min_minutes = 60
                                delta_minutes = (check_utc - open_att.check_in).total_seconds() / 60.0
                                if delta_minutes < min_minutes:
                                    env['hr.temp.attendance'].sudo().create({
                                        'employee_id': employee.id,
                                        'check_date': check_utc,
                                        'employee_type': employee.employee_type,
                                        'employee_type_shift': employee.type_shift, 
                                        'notes': 'Intento marcar la salida, debe ser al menos %d minutos después de la entrada (%s)' % (min_minutes, open_att.check_in.strftime("%Y-%m-%d %H:%M")),
                                    })
                                    message += f'--la salida debe ser al menos {min_minutes} minutos después de la entrada ({open_att.check_in.strftime("%Y-%m-%d %H:%M")})'
                                    return {'success': False, 'error': message, 'received': data}
                                open_att.write({'check_out': check_utc})
                                message += f' (asistencia cerrada: {open_att.id})'
                            else:
                                open_att = hr_attendance.create({
                                    'employee_id': employee.id,
                                    'check_in': check_utc,
                                    'create_lector': True,
                                })
                                message += f'--asistencia abierta: {open_att.id} (empleado en borrador)'
                elif open_method == 'FINGERPRINT':
                    if not employee:
                        employee = hr_employee.create({
                            'id_lector': employee_dni,
                            'dni': dni,
                            'name': employee_name,
                            'employee_type': 'eventual',
                            'type_shift': type_shift,
                            'state': 'active',
                        })
                        if employee.type_shift == 'day':
                            if check_utc > start_limit_day:
                                # lo registro en el hr temp attendance
                                env['hr.temp.attendance'].sudo().create({
                                    'employee_id': employee.id,
                                    'check_date': check_utc,
                                    'employee_type': employee.employee_type,
                                    'employee_type_shift': employee.type_shift,
                                    'notes': 'Intento marcar Entrada fuera del rango diurno (%s-%s)' % (start_limit_day.strftime("%H:%M"), end_limit_day.strftime("%H:%M")),
                                })
                                message += f'--asistencia fuera de rango diurno ({start_limit_day.strftime("%H:%M")}-{end_limit_day.strftime("%H:%M")})'
                                return {'success': False, 'error': message, 'received': data}
                            else:
                                if check_utc > start_limit_day_inicio_marcado:
                                    open_att = hr_attendance.create({
                                        'employee_id': employee.id,
                                        'check_in': check_utc,
                                        'create_lector': True,
                                    })
                                else:
                                    message += '--asistencia fuera del rango diurno de inicio de marcado'
                                    return {'success': False, 'error': message, 'received': data}
                        else:  # night
                            if check_utc > start_limit_night:
                                # lo registro en el hr temp attendance
                                env['hr.temp.attendance'].sudo().create({
                                    'employee_id': employee.id,
                                    'check_date': check_utc,
                                    'employee_type': employee.employee_type,
                                    'employee_type_shift': employee.type_shift,
                                    'notes': 'Intento marcar Entrada fuera del rango nocturno (%s-%s)' % (start_limit_night.strftime("%H:%M"), end_limit_night.strftime("%H:%M")),
                                })
                                message += f'--asistencia fuera de rango nocturno ({start_limit_night.strftime("%H:%M")}-{end_limit_night.strftime("%H:%M")})'
                                return {'success': False, 'error': message, 'received': data}
                            else:
                                if check_utc > start_limit_night_inicio_marcado:
                                    open_att = hr_attendance.create({
                                        'employee_id': employee.id,
                                        'check_in': check_utc,
                                        'create_lector': True,
                                    })
                                else:
                                    message += '--asistencia fuera del rango nocturno de inicio de marcado'
                                    return {'success': False, 'error': message, 'received': data}
                        message += f'--asistencia abierta: {open_att.id} (empleado en borrador)'
                    else:
                        if employee.employee_type == 'eventual':
                            # Limites del día (para agrupar por día local)
                            open_att = hr_attendance.search([
                                ('employee_id', '=', employee.id),
                                ('check_out', '=', False),
                                ('blocked', '=', False)], limit=1, order='check_in desc')
                            if employee.type_shift == 'day':
                                if open_att:
                                    if open_att.check_in.date() == check_utc.date():
                                        min_minutes = 60
                                        delta_minutes = (check_utc - open_att.check_in).total_seconds() / 60.0
                                        if delta_minutes < min_minutes:
                                            message += f'--la salida debe ser al menos {min_minutes} minutos después de la entrada ({open_att.check_in.strftime("%Y-%m-%d %H:%M")})'
                                            return {'success': False, 'error': message, 'received': data}
                                        if dow == 5:  # Sábado
                                            end_limit_day = end_limit_day - timedelta(hours=2)
                                            if check_utc > end_limit_day:
                                                env['hr.temp.attendance'].sudo().create({
                                                    'employee_id': employee.id,
                                                    'check_date': check_utc,
                                                    'employee_type': employee.employee_type,
                                                    'employee_type_shift': employee.type_shift,
                                                    'notes': 'Intento marcar la salida fuera del rango diurno (%s-%s)' % (start_limit_day.strftime("%H:%M"), end_limit_day.strftime("%H:%M")),
                                                })
                                                message += f'--asistencia fuera del limite de salida diurno ({end_limit_day.strftime("%H:%M")})'
                                                return {'success': False, 'error': message, 'received': data}
                                        if dow in [0,1,2,3,4]:  # Lunes a Viernes
                                            if check_utc > end_limit_day:
                                                env['hr.temp.attendance'].sudo().create({
                                                    'employee_id': employee.id,
                                                    'check_date': check_utc,
                                                    'employee_type': employee.employee_type,
                                                    'employee_type_shift': employee.type_shift,
                                                    'notes': 'Intento marcar la salida fuera del rango diurno (%s-%s)' % (start_limit_day.strftime("%H:%M"), end_limit_day.strftime("%H:%M")),
                                                })
                                                message += f'--asistencia fuera del limite de salida diurno ({end_limit_day.strftime("%H:%M")})'
                                                return {'success': False, 'error': message, 'received': data}
                                        # Cerrar asistencia abierta
                                        open_att.write({'check_out': check_utc})
                                        message += f' (asistencia cerrada: {open_att.id})'
                                    else:
                                        #bloquear la asistencia abierta anterior
                                        open_att.write({'blocked': True})
                                        if dow in [0,1,2,3,4]:  # Lunes a Viernes
                                            if check_utc > start_limit_day:
                                                env['hr.temp.attendance'].sudo().create({
                                                    'employee_id': employee.id,
                                                    'check_date': check_utc,
                                                    'employee_type': employee.employee_type,
                                                })
                                                message += f'--asistencia fuera del limite de ingreso diurno ({start_limit_day.strftime("%H:%M")})'
                                                return {'success': False, 'error': message, 'received': data}
                                        elif dow == 5:  # Sábado
                                            start_limit_day = start_limit_day + timedelta(hours=1)
                                            if check_utc > start_limit_day:
                                                env['hr.temp.attendance'].sudo().create({
                                                    'employee_id': employee.id,
                                                    'check_date': check_utc,
                                                    'employee_type': employee.employee_type,
                                                })
                                                message += f'--asistencia fuera del limite de salida diurno ({end_limit_day.strftime("%H:%M")})'
                                                return {'success': False, 'error': message, 'received': data}
                                        # Crear asistencia abierta
                                        if check_utc > start_limit_day_inicio_marcado:
                                            open_att = hr_attendance.create({
                                                'employee_id': employee.id,
                                                'check_in': check_utc,
                                                'create_lector': True,
                                            })
                                            message += f' (asistencia abierta: {open_att.id})'
                                        else:
                                            message += '--asistencia fuera del rango diurno de inicio de marcado'
                                            return {'success': False, 'error': message, 'received': data}
                                else:
                                    if dow in [0,1,2,3,4]:  # Lunes a Viernes
                                        if check_utc > start_limit_day:
                                            env['hr.temp.attendance'].sudo().create({
                                                'employee_id': employee.id,
                                                'check_date': check_utc,
                                                'employee_type': employee.employee_type,
                                                'employee_type_shift': employee.type_shift,
                                                'notes': 'Intento marcar Entrada fuera del rango diurno (%s-%s)' % (start_limit_day.strftime("%H:%M"), end_limit_day.strftime("%H:%M")),
                                            })
                                            message += f'--asistencia fuera del limite de ingreso diurno ({start_limit_day.strftime("%H:%M")})'
                                            return {'success': False, 'error': message, 'received': data}
                                    elif dow == 5:  # Sábado
                                        start_limit_day = start_limit_day + timedelta(hours=1)
                                        if check_utc > start_limit_day:
                                            env['hr.temp.attendance'].sudo().create({
                                                'employee_id': employee.id,
                                                'check_date': check_utc,
                                                'employee_type': employee.employee_type,
                                                'employee_type_shift': employee.type_shift,
                                                'notes': 'Intento marcar la salida fuera del rango diurno (%s-%s)' % (start_limit_day.strftime("%H:%M"), end_limit_day.strftime("%H:%M")),
                                            })
                                            message += f'--asistencia fuera del limite de salida diurno ({end_limit_day.strftime("%H:%M")})'
                                            return {'success': False, 'error': message, 'received': data}
                                    if check_utc > start_limit_day_inicio_marcado:
                                        # Crear asistencia abierta
                                        open_att = hr_attendance.create({
                                            'employee_id': employee.id,
                                            'check_in': check_utc,
                                            'create_lector': True,
                                        })
                                        message += f' (asistencia abierta: {open_att.id})'
                                    else:
                                        message += '--asistencia fuera del rango diurno de inicio de marcado'
                                        return {'success': False, 'error': message, 'received': data}
                            elif employee.type_shift == 'night':
                                if open_att:
                                    # Validar el rango de la salida nocturna
                                    min_minutes = 60
                                    delta_minutes = (check_utc - open_att.check_in).total_seconds() / 60.0
                                    if delta_minutes < min_minutes:
                                        message += f'--la salida debe ser al menos {min_minutes} minutos después de la entrada ({open_att.check_in.strftime("%Y-%m-%d %H:%M")})'
                                        return {'success': False, 'error': message, 'received': data}
                                    if check_utc > end_limit_night:
                                        env['hr.temp.attendance'].sudo().create({
                                            'employee_id': employee.id,
                                            'check_date': check_utc,
                                            'employee_type': employee.employee_type,
                                        })
                                        message += f'--asistencia fuera de rango de salida del horario nocturno ({end_limit_night.strftime("%H:%M")})'
                                        return {'success': False, 'error': message, 'received': data}
                                    # permitir mismo día o día siguiente como máximo
                                    delta_days = (check_utc.date() - open_att.check_in.date()).days
                                    if delta_days > 1:
                                        message += ' --la salida nocturna debe ser el mismo día o el día siguiente (máx. 1 día de diferencia)'
                                        return {'success': False, 'error': message, 'received': data}
                                    if check_utc <= open_att.check_in:
                                        env['hr.temp.attendance'].sudo().create({
                                            'employee_id': employee.id,
                                            'check_date': check_utc,
                                            'employee_type': employee.employee_type,
                                            'employee_type_shift': employee.type_shift,
                                            'notes': 'Intento marcar la salida nocturna anterior/igual a la entrada (%s)' % (open_att.check_in.strftime("%Y-%m-%d %H:%M")), 
                                        })
                                        message += ' --la salida no puede ser anterior/igual a la entrada'
                                        return {'success': False, 'error': message, 'received': data}
                                    open_att.write({'check_out': check_utc})
                                    message += f' (asistencia nocturna cerrada: {open_att.id})'
                                else:
                                    if check_utc > start_limit_night:
                                        env['hr.temp.attendance'].sudo().create({
                                            'employee_id': employee.id,
                                            'check_date': check_utc,
                                            'employee_type': employee.employee_type,
                                            'employee_type_shift': employee.type_shift,
                                            'notes': 'Intento marcar la salida fuera del rango nocturno (%s-%s)' % (start_limit_night.strftime("%H:%M"), end_limit_night.strftime("%H:%M")),
                                        })
                                        message += f'--asistencia fuera de rango nocturno ({start_limit_night.strftime("%H:%M")}-{end_limit_night.strftime("%H:%M")})'
                                        return {'success': False, 'error': message, 'received': data}
                                    if check_utc > start_limit_night_inicio_marcado:
                                        # Crear asistencia abierta
                                        open_att = hr_attendance.create({
                                            'employee_id': employee.id,
                                            'check_in': check_utc,
                                            'create_lector': True,
                                        })
                                        message += f' (asistencia abierta: {open_att.id})'
                                    else:
                                        message += '--asistencia fuera del rango nocturno de inicio de marcado'
                                        return {'success': False, 'error': message, 'received': data}
                return {'success': True, 'message': message, 'status_code': 200, 'received': data}
            except ValidationError as ve:
                return {'success': False, 'error': str(ve), 'error_class': ve.__class__.__name__, 'received': data, 'status_code': 400}
            except Exception as e:
                # rollback explícito por si quedó algo a medio camino
                env.cr.rollback()
                return {'success': False, 'error': str(e), 'received': data, 'status_code': 500}