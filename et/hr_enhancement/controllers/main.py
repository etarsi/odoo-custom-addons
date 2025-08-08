from odoo import http
from odoo.http import request, Response
from odoo.exceptions import ValidationError
from datetime import datetime
import traceback
import json

BA_TZ_PARAM = 'America/Argentina/Buenos_Aires'  # si luego querés hacerlo configurable

def _get_param_float(key, default=None):
    raw = request.env['ir.config_parameter'].sudo().get_param(key)
    if raw in (None, ''):
        return default
    try:
        # soporta "07:30" -> 7.5; "7.5" -> 7.5
        if ':' in str(raw):
            h, m = str(raw).split(':', 1)
            return int(h) + (int(m) / 60.0)
        return float(raw)
    except Exception:
        # si no se puede parsear, devolvés None para que falle la validación más adelante
        return default

class HrAttendanceController(http.Controller):

    @http.route('/hr_enhancement/attendance', type='json', auth='public', csrf=False, methods=['POST'])
    def attendance_webhook(self, **kw):
        # Para ver lo que llega siempre
        data = request.jsonrequest or {}
        debug = bool(data.get('debug'))  # si mandás "debug:true" en el body
        try:
            employee_dni = data.get('dni')
            employee_name = data.get('name')
            # Si querés usar la hora enviada, usa data.get('check'); ahora uso hora del servidor:
            check_time = datetime.now()  # Odoo guarda naive UTC

            # Paramétricas (seguras)
            p_day_start   = _get_param_float('hr_enhancement.hour_start_day_check')
            p_day_end     = _get_param_float('hr_enhancement.hour_end_day_check')
            p_night_start = _get_param_float('hr_enhancement.hour_start_night_check')
            p_night_end   = _get_param_float('hr_enhancement.hour_end_night_check')

            # Validaciones simples de entrada
            if not employee_dni:
                raise ValidationError("Falta 'dni' en el payload.")
            if not employee_name:
                # si tu modelo crea sin name, podés omitir; acá lo pido para ejemplo
                raise ValidationError("Falta 'name' en el payload.")

            # Buscar por DNI (NO uses name en el dominio para evitar misses)
            emp = request.env['hr.employee'].sudo().search([('dni', '=', employee_dni)], limit=1)
            created_emp = False
            if not emp:
                emp = request.env['hr.employee'].sudo().create({
                    'dni': employee_dni,
                    'name': employee_name,
                    # 'employee_type': 'eventual',
                    # 'state': 'activo',
                })
                created_emp = True

            att = request.env['hr.attendance'].sudo().create({
                'employee_id': emp.id,
                'check_in': check_time,  # naive UTC
            })

            return {
                'success': True,
                'message': 'Asistencia registrada',
                'employee': {'id': emp.id, 'dni': employee_dni, 'name': emp.name, 'created': created_emp},
                'attendance': {'id': att.id, 'check_in': check_time.strftime('%Y-%m-%d %H:%M:%S')},
                'received': data,  # eco del payload
                'params': {
                    'day_start': p_day_start, 'day_end': p_day_end,
                    'night_start': p_night_start, 'night_end': p_night_end,
                },
            }

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
