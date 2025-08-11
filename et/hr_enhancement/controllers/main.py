from odoo import http
from odoo.http import request, Response
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import pytz, traceback, json

BA_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

def _get_param_float(key, default=None):
    """Lee paramétricas. Acepta '07:30' -> 7.5 o '7.5' -> 7.5."""
    raw = request.env['ir.config_parameter'].sudo().get_param(key)
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
    
def _float_to_hm(hf):
    h = int(hf)
    m = int(round((hf - h) * 60))
    if m == 60:
        h += 1; m = 0
    return h % 24, m

def _in_window(hf, start_f, end_f):
    """Valida si hf (0..24) cae en [start_f, end_f) soportando cruce de medianoche."""
    if start_f is None or end_f is None:
        return True
    if not (0 <= hf < 24):
        return False
    if start_f <= end_f:
        return start_f <= hf < end_f
    # cruza medianoche
    return hf >= start_f or hf < end_f

def _to_utc_naive(dt_local_aware):
    """Aware (con tz) -> naive UTC (lo que guarda Odoo)."""
    return dt_local_aware.astimezone(pytz.UTC).replace(tzinfo=None)

def _day_bounds_utc(check_local):
    """Inicio y fin del día (local) en UTC naive."""
    start_local = check_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local   = check_local.replace(hour=23, minute=59, second=59, microsecond=999999)
    return _to_utc_naive(start_local), _to_utc_naive(end_local)

def _window_bounds_utc(check_local, start_f, end_f):
    """Devuelve (inicio_ventana_utc_naive, fin_ventana_utc_naive) para el día de check_local."""
    sh, sm = _float_to_hm(start_f)
    eh, em = _float_to_hm(end_f)
    w_start_local = check_local.replace(hour=sh, minute=sm, second=0, microsecond=0)
    w_end_local   = check_local.replace(hour=eh, minute=em, second=0, microsecond=0)
    if start_f is not None and end_f is not None and start_f > end_f:
        # cruza medianoche: fin pasa al día siguiente
        w_end_local += timedelta(days=1)
    return _to_utc_naive(w_start_local), _to_utc_naive(w_end_local)


class HrAttendanceController(http.Controller):

    @http.route('/hr_enhancement/attendance', type='json', auth='public', csrf=False, methods=['POST'])
    def attendance_webhook(self, **kw):
        # Para ver lo que llega siempre
        data = request.jsonrequest or {}
        debug = bool(data.get('debug'))  # si mandás "debug:true" en el body
        try:
            employee_dni = data.get('dni')
            employee_name = data.get('name')
            check_time = data.get('check_time')
            open_method = data.get('openMethod')
            check_local = BA_TZ.localize(check_time)
            check_utc   = _to_utc_naive(check_local)
            
            # Paramétricas (seguras)
            p_day_start   = _get_param_float('hr_enhancement.hour_start_day_check')
            p_day_end     = _get_param_float('hr_enhancement.hour_end_day_check')
            p_night_start = _get_param_float('hr_enhancement.hour_start_night_check')
            p_night_end   = _get_param_float('hr_enhancement.hour_end_night_check')
            hr_attendance = request.env['hr.attendance'].sudo()
            hr_employee = request.env['hr.employee'].sudo()
            employee = hr_employee.search([('dni', '=', employee_dni)], limit=1)
            message = f'Asistencia registrada para {employee_name} ({employee_dni}) a las {check_local.strftime("%Y-%m-%d %H:%M:%S")}'
            resp = {
                'success': True,
                'message': message,
            }
            if open_method == 'FACE_RECOGNITION':
                return Response(json.dumps(resp), status=200, mimetype='application/json')

            elif open_method == 'FINGERPRINT':
                if not employee:
                    employee = hr_employee.create({
                        'dni': employee_dni,
                        'name': employee_name,
                        'employee_type': 'eventual',
                        'state': 'activo',
                    })
                    open_att = hr_attendance.create({
                        'employee_id': employee.id,
                        'check_in': check_utc,  # naive UTC
                    })
                    message += f'asistencia abierta: {open_att.id}'
                else:
                    hh = check_local.hour + check_local.minute/60.0 + check_local.second/3600.0
                    if employee.type_shift == 'day':
                        in_day = _in_window(hh, p_day_start, p_day_end)
                        if not in_day:
                            raise ValidationError(f'Hora fuera de rango diurno. hora={hh:.2f}, rango=[{p_day_start:.2f},{p_day_end:.2f})')
                        # Limites del día (para agrupar por día local)
                        day_start_utc, day_end_utc = _day_bounds_utc(check_local)
                        open_att = hr_attendance.search([
                            ('employee_id', '=', employee.id),
                            ('check_in', '>=', day_start_utc),
                            ('check_in', '<=', day_end_utc),
                        ], limit=1)
                        if open_att:
                            open_att.write({'check_out': check_utc})
                            message += f' (asistencia cerrada: {open_att.id})'
                        else:
                            open_att = hr_attendance.create({
                                'employee_id': employee.id,
                                'check_in': check_utc,
                            })
                            message += f' (asistencia abierta: {open_att.id})'
                    elif employee.type_shift == 'night':
                        in_night = _in_window(hh, p_night_start, p_night_end)
                        if not in_night:
                            raise ValidationError(f'Hora fuera de rango nocturno. hora={hh:.2f}, rango=[{p_night_start:.2f},{p_night_end:.2f})')
                        # Limites del día (para agrupar por día local)
                        day_start_utc, day_end_utc = _day_bounds_utc(check_local)
                        open_att = hr_attendance.search([
                            ('employee_id', '=', employee.id),
                            ('check_in', '>=', day_start_utc),
                            ('check_in', '<=', day_end_utc),
                        ], limit=1)
                        if open_att:
                            open_att.write({'check_out': check_utc})
                            message += f' (asistencia cerrada: {open_att.id})'
                        else:
                            open_att = hr_attendance.create({
                                'employee_id': employee.id,
                                'check_in': check_utc,
                            })
                            message += f' (asistencia abierta: {open_att.id})'

            return Response(json.dumps(resp), status=200, mimetype='application/json')

        except ValidationError as ve:
            # Error de validación del negocio → 400
            resp = {
                'success': False,
                'error': str(ve),
                'error_class': ve.__class__.__name__,
                'received': data,
            }
            if debug:
                resp['traceback'] = traceback.format_exc()
            return Response(json.dumps(resp), status=400, mimetype='application/json')

        except Exception as e:
            # Cualquier otra excepción → 500 y devolvés detalle
            resp = {
                'success': False,
                'error': str(e),
                'error_class': e.__class__.__name__,
                'received': data,
            }
            if debug:
                resp['traceback'] = traceback.format_exc()
            # rollback explícito por si quedó algo a medio camino
            request.env.cr.rollback()
            return Response(json.dumps(resp), status=500, mimetype='application/json')
