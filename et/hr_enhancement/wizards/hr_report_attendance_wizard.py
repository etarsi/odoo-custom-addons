from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter
from . import excel

class HrReportAttendanceWizard(models.TransientModel):
    _name = 'hr.report.attendance.wizard'
    _description = 'Wizard para Exportar Asistencias a Excel'

    date_start = fields.Date('Fecha inicio', required=True, default=fields.Date.context_today)
    date_end = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados',
    )
    employee_type = fields.Selection(
        string='Tipo de Empleado',
        selection=[('employee', 'Empleado'), ('eventual', 'Eventual'), ('all', 'Todos')], default='all'
    )
    employee_type_shift = fields.Selection(
        string='Turno Asignado',
        selection=[('day', 'Día'), ('night', 'Noche'), ('all', 'Todos')], default='all'
    )

    # si selecciona employe_type debe limpiar el employee_ids
    @api.onchange('employee_type', 'employee_type_shift')
    def _onchange_employee_type(self):
        if self.employee_type != 'all':
            self.employee_ids = False   

    def _to_local(self, dt):
        return fields.Datetime.context_timestamp(self, dt) if dt else None

    # Generar el reporte en Excel
    def action_generar_excel(self):
        # Crear un buffer en memoria
        output = io.BytesIO()
        # Crear el archivo Excel
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Asistencias')
        # Agrupados por rangos consecutivos con mismo ancho
        worksheet.set_column(0, 0, 30)   # Empleado
        worksheet.set_column(1, 1, 15)   # Fecha 
        worksheet.set_column(2, 2, 15)   # Dia Trabajado
        worksheet.set_column(3, 3, 15)   # Fecha Ingreso
        worksheet.set_column(4, 4, 15)   # Fecha Salida
        worksheet.set_column(5, 5, 15)   # Horas Trabajadas
        worksheet.set_column(6, 6, 15)   # Horas Extras
        worksheet.set_column(7, 7, 15)   # Horas Feriado
        worksheet.set_column(8, 8, 20)   # Tipo de Empleado
        worksheet.set_column(9, 9, 20)   # Turno Asignado

        #formato de celdas
        formato_encabezado = excel.formato_encabezado(workbook)
        formato_celdas_izquierda = excel.formato_celda_izquierda(workbook)
        formato_celdas_derecha = excel.formato_celda_derecha(workbook)
        formato_celdas_decimal = excel.formato_celda_decimal(workbook)
        fmt_emp = workbook.add_format({'bold': True, 'bg_color': "#5384AF", 'border': 1, 'align': 'left'})
        fmt_total = workbook.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'align': 'ringht'})
            
        # Escribir datos
        rango_start = self.date_start.strftime('%d/%m/%Y')
        rango_end = self.date_end.strftime('%d/%m/%Y')
        #colocar un titulo que diga SEBIGUS SRL en la primera fila centrado y en negrita de la a columna A a la E
        worksheet.merge_range(0, 0, 0, 9, 'SEBIGUS SRL', formato_encabezado)
        #colocar un subtitulo que diga REPORTE DE ASISTENCIA en la segunda fila centrado y en negrita de la a columna A a la E
        worksheet.merge_range(1, 0, 1, 9, 'REPORTE DE ASISTENCIA', formato_encabezado)
        #colocar un subtitulo que diga el rango de fechas en la tercera fila centrado y en negrita de la a columna A a la E
        worksheet.merge_range(2, 0, 2, 9, f'Rango de Fechas: {rango_start} a {rango_end}', formato_encabezado)
        # Escribir encabezados
        header_row = 4
        worksheet.write(header_row, 0, 'EMPLEADO', formato_encabezado)
        worksheet.write(header_row, 1, 'FECHA', formato_encabezado)
        worksheet.write(header_row, 2, 'INGRESO', formato_encabezado)
        worksheet.write(header_row, 3, 'SALIDA', formato_encabezado)
        worksheet.write(header_row, 4, 'DÍAS TRABAJADOS', formato_encabezado)
        worksheet.write(header_row, 5, 'H. TRABAJADAS', formato_encabezado)
        worksheet.write(header_row, 6, 'H. 50%', formato_encabezado)
        worksheet.write(header_row, 7, 'H. 100%', formato_encabezado)
        worksheet.write(header_row, 8, 'TIPO DE EMPLEADO', formato_encabezado)
        worksheet.write(header_row, 9, 'TURNO ASIGNADO', formato_encabezado)
        # Buscar facturas en el rango de fechas
        domain = [
            ('check_in', '>=', self.date_start),
            ('check_in', '<=', self.date_end),
            '|', ('check_out', '=', False), ('check_out', '<=', self.date_end),
        ]
        if not self.date_start or not self.date_end:
            raise ValidationError("La Fecha de Inicio y Final es Requerido")
        if self.date_end < self.date_start:
            raise ValidationError("La Fecha Final del reporte de facturas, no puede ser menor a la Fecha de Inicio")
        
        # Recolectar los tipos seleccionados en una lista
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        if self.employee_type != 'all':
            domain.append(('employee_type', '=', self.employee_type))
        if self.employee_type_shift != 'all':
            domain.append(('employee_type_shift', '=', self.employee_type_shift))
        attendances = self.env['hr.attendance'].search(domain, order="employee_id, check_in")
        row = header_row + 1
        current_emp_id = False

        # --- acumular totales en Python por empleado ---
        totales_por_emp = {}
        for att in attendances:
            emp_id = att.employee_id.id
            if emp_id not in totales_por_emp:
                totales_por_emp[emp_id] = {'wh': 0.0, 'ot': 0.0, 'hh': 0.0}
            totales_por_emp[emp_id]['wh'] += att.worked_hours or 0.0
            totales_por_emp[emp_id]['ot'] += att.overtime or 0.0
            totales_por_emp[emp_id]['hh'] += att.holiday_hours or 0.0

        for attendance in attendances:
            emp = attendance.employee_id
            emp_id = emp.id
            # 2) cuando cambia de empleado, escribo la "cabecera" con los totales
            if current_emp_id and emp.id != current_emp_id:
                tot_prev = totales_por_emp[current_emp_id]
                worksheet.merge_range(row, 0, row, 4, " ", fmt_total)
                worksheet.write(row, 5, tot_prev['wh'], fmt_total)
                worksheet.write(row, 6, tot_prev['ot'], fmt_total)
                worksheet.write(row, 7, tot_prev['hh'], fmt_total)
                worksheet.merge_range(row, 8, row, 9, " ", fmt_total)
                row += 1  # línea en blanco después del total
                # encabezado del nuevo empleado
                worksheet.merge_range(row, 0, row, 9, emp.name or '—', fmt_emp)
                row += 1
            # --- primer registro de un empleado (no hay bloque previo) ---
            if not current_emp_id:
                worksheet.merge_range(row, 0, row, 9, emp.name or '—', fmt_emp)
                row += 1
            current_emp_id = emp_id
            
            weekday_label = dict(attendance._fields['day_of_week'].selection).get(
                attendance.day_of_week, ''
            )
            # dentro del loop
            ci_local = self._to_local(attendance.check_in)
            co_local = self._to_local(attendance.check_out)
            # si querés también la fecha local: 
            fecha = ci_local.strftime('%d/%m/%Y') if ci_local else ''
            # horas en la tz del usuario de Odoo (o la del contexto)
            ingreso = ci_local.strftime('%H:%M:%S') if ci_local else ''
            salida  = co_local.strftime('%H:%M:%S') if co_local else ''
            tipo_empleado = 'Empleado' if attendance.employee_type == 'employee' else 'Eventual' if attendance.employee_type == 'eventual' else ''
            turno_asignado = 'Día' if attendance.employee_type_shift == 'day' else 'Noche' if attendance.employee_type_shift == 'night' else ''
            #como colocar una linea separacion entre empleados
            worksheet.write(row, 0, attendance.employee_id.name, formato_celdas_izquierda)
            worksheet.write(row, 1, fecha, formato_celdas_derecha)
            worksheet.write(row, 2, ingreso, formato_celdas_derecha)
            worksheet.write(row, 3, salida, formato_celdas_derecha)
            worksheet.write(row, 4, weekday_label, formato_celdas_derecha)
            worksheet.write(row, 5, attendance.worked_hours or 0, formato_celdas_derecha)
            worksheet.write(row, 6, attendance.overtime or 0, formato_celdas_derecha)
            worksheet.write(row, 7, attendance.holiday_hours or 0, formato_celdas_derecha)
            worksheet.write(row, 8, tipo_empleado, formato_celdas_izquierda)
            worksheet.write(row, 9, turno_asignado, formato_celdas_izquierda)
            row += 1
        # --- SUBTOTAL para el último empleado ---
        if current_emp_id:
            tot_prev = totales_por_emp[current_emp_id]
            worksheet.merge_range(row, 0, row, 4, " ", fmt_total)
            worksheet.write(row, 5, tot_prev['wh'], fmt_total)
            worksheet.write(row, 6, tot_prev['ot'], fmt_total)
            worksheet.write(row, 7, tot_prev['hh'], fmt_total)
            worksheet.merge_range(row, 8, row, 9, " ", fmt_total)
            row += 1
        
        workbook.close()
        output.seek(0)
        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'reporte_asistencia.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': f'reporte_asistencia.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        # Retornar acción para descargar el archivo
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self'
        }