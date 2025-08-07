from odoo import http
from odoo.http import request, Response
import json

class HrAttendanceController(http.Controller):

    @http.route('/hr_enhancement/attendance', type='json', auth='public', csrf=False, methods=['POST'])
    def attendance_webhook(self, **kw):
        try:
            # El JSON llega como un diccionario de Python en "request.jsonrequest"
            data = request.jsonrequest
            employee_dni = data.get('dni')
            employee_name = data.get('name')
            check = data.get('check')
            # TODO: podés validar o procesar el dato acá
            # Por ejemplo, crear el registro de asistencia:
            employee = request.env['hr.employee'].sudo().search([('dni', '=', employee_dni), ('name', '=', employee_name)], limit=1)
            if not employee:
                employee = request.env['hr.employee'].sudo().create({
                    'dni': employee_dni,
                    'name': employee_name,
                })
                request.env['hr.attendance'].sudo().create({
                    'employee_id': employee.id,
                    'check_in': check,
                })
            else:
                request.env['hr.attendance'].sudo().create({
                    'employee_id': employee.id,
                    'check_in': check,
                })
            return {'success': True, 'message': 'Se registró la asistencia correctamente'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
