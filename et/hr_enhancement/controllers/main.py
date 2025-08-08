from odoo import http
from odoo.http import request, Response
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time
import json
import pytz

class HrAttendanceController(http.Controller):

    @http.route('/hr_enhancement/attendance', type='json', auth='public', csrf=False, methods=['POST'])
    def attendance_webhook(self, **kw):
        try:
            # El JSON llega como un diccionario de Python en "request.jsonrequest"
            data = request.jsonrequest
            employee_dni = data.get('dni')
            employee_name = data.get('name')
            check_time = datetime.now()
            print(f"Recibido webhook de asistencia: DNI {employee_dni}, Nombre {employee_name}, Hora {check_time}")
            
            
            #sacar configuracion de parametricas
            param_hour_start_day_check = float(request.env['ir.config_parameter'].sudo().get_param('hr_enhancement.hour_start_day_check'))
            param_hour_end_day_check = float(request.env['ir.config_parameter'].sudo().get_param('hr_enhancement.hour_end_day_check'))
            param_hour_start_night_check = float(request.env['ir.config_parameter'].sudo().get_param('hr_enhancement.hour_start_night_check'))
            param_hour_end_night_check = float(request.env['ir.config_parameter'].sudo().get_param('hr_enhancement.hour_end_night_check'))
            # TODO: podés validar o procesar el dato acá
            # Por ejemplo, crear el registro de asistencia:
            employee = request.env['hr.employee'].sudo().search([('dni', '=', employee_dni), ('name', '=', employee_name)], limit=1)
            if not employee:
                print(f"Empleado no encontrado: DNI {employee_dni}, Nombre {employee_name}")
                employee = request.env['hr.employee'].sudo().create({
                    'dni': employee_dni,
                    'name': employee_name,
                    'employee_type': 'eventual',
                    'state': 'activo'
                })
                request.env['hr.attendance'].sudo().create({
                    'employee_id': employee.id,
                    #coloca la hora actual como hora de entrada
                    'check_in': check_time,
                })
            else:
                print(f"Empleado encontrado: {employee.name} (DNI: {employee.dni})")
                request.env['hr.attendance'].sudo().create({
                    'employee_id': employee.id,
                    'check_in': check_time,
                })
            return {'success': True, 'message': 'Se registró la asistencia correctamente'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
