from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter
from . import excel

MESES_ES = {
    '01': 'Enero',
    '02': 'Febrero',
    '03': 'Marzo',
    '04': 'Abril',
    '05': 'Mayo',
    '06': 'Junio',
    '07': 'Julio',
    '08': 'Agosto',
    '09': 'Septiembre',
    '10': 'Octubre',
    '11': 'Noviembre',
    '12': 'Diciembre',
}

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
    
    # Generar el reporte en Excel
    def action_generar_excel(self):
        # Crear un buffer en memoria
        output = io.BytesIO()
        # Crear el archivo Excel
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Asistencias')
        # Agrupados por rangos consecutivos con mismo ancho
        worksheet.set_column(0, 0, 10)   # nro correlativo
        worksheet.set_column(0, 0, 20)   # Empleado
        worksheet.set_column(1, 2, 15)   # Fecha Ingreso
        worksheet.set_column(2, 2, 12)   # Fecha Salida
        worksheet.set_column(3, 3, 10)   # Tipo de Empleado
        worksheet.set_column(4, 4, 15)   # Turno Asignado
        
        #formato de celdas
        formato_encabezado = excel.formato_encabezado(workbook)
        formato_celdas_izquierda = excel.formato_celda_izquierda(workbook)
        formato_celdas_derecha = excel.formato_celda_derecha(workbook)
        formato_celdas_decimal = excel.formato_celda_decimal(workbook)
        # Escribir encabezados
        worksheet.write(0, 0, 'NRO', formato_encabezado)
        worksheet.write(0, 1, 'EMPLEADO', formato_encabezado)
        worksheet.write(0, 2, 'INGRESO', formato_encabezado)
        worksheet.write(0, 3, 'SALIDA', formato_encabezado)
        worksheet.write(0, 4, 'TIPO DE EMPLEADO', formato_encabezado)
        worksheet.write(0, 5, 'TURNO ASIGNADO', formato_encabezado)

        # Buscar facturas en el rango de fechas
        domain = [
            ('check_in', '>=', self.date_start),
            ('check_out', '<=', self.date_end),
        ]
        if not self.date_start or not self.date_end:
            raise ValidationError("La Fecha de Inicio y Final es Requerido")
        if self.date_end < self.date_start:
            raise ValidationError("La Fecha Final del reporte de facturas, no puede ser menor a la Fecha de Inicio")
        
        # Recolectar los tipos seleccionados en una lista
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        if self.employee_type != 'all':
            domain.append(('employee_type', '=', self.employee_type))
        if self.employee_type_shift != 'all':
            domain.append(('employee_type_shift', '=', self.employee_type_shift))
        attendances = self.env['hr.attendance'].search(domain)
        # Escribir datos
        rango_start = self.date_start.strftime('%Y-%m-%d')
        rango_end = self.date_end.strftime('%Y-%m-%d')
        row = 1
        correlativo = 1
        #colocar un titulo que diga SEBIGUS SRL en la primera fila centrado y en negrita de la a columna A a la F
        worksheet.merge_range(0, 0, 0, 5, 'SEBIGUS SRL', formato_encabezado)
        #colocar un subtitulo que diga REPORTE DE ASISTENCIA en la segunda fila centrado y en negrita de la a columna A a la F
        worksheet.merge_range(1, 0, 1, 5, 'REPORTE DE ASISTENCIA', formato_encabezado)
        #colocar un subtitulo que diga el rango de fechas en la tercera fila centrado y en negrita de la a columna A a la F
        worksheet.merge_range(2, 0, 2, 5, f'Rango de Fechas: {rango_start} a {rango_end}', formato_encabezado)
        row = 4  # Empezar a escribir datos desde la fila 5 (índice 4)
        for attendance in attendances:
            # Fechas formateadas
            ingreso = attendance.check_in.strftime('%Y-%m-%d %H:%M:%S') if attendance.check_in else ''
            salida = attendance.check_out.strftime('%Y-%m-%d %H:%M:%S') if attendance.check_out else ''
            tipo_empleado = 'Empleado' if attendance.employee_type == 'employee' else 'Eventual' if attendance.employee_type == 'eventual' else ''
            turno_asignado = 'Día' if attendance.employee_type_shift == 'day' else 'Noche' if attendance.employee_type_shift == 'night' else ''
            
            worksheet.write(row, 0, correlativo, formato_celdas_izquierda)
            worksheet.write(row, 1, attendance.employee_id.name, formato_celdas_derecha)
            worksheet.write(row, 2, ingreso, formato_celdas_derecha)
            worksheet.write(row, 3, salida, formato_celdas_derecha)
            worksheet.write(row, 4, tipo_empleado, formato_celdas_izquierda)
            worksheet.write(row, 5, turno_asignado, formato_celdas_izquierda)
            correlativo += 1
            row += 1
        workbook.close()
        output.seek(0)
        # Codificar el archivo en base64
        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'reporte_asistencia.xlsx',  # Nombre del archivo con fecha
            'type': 'binary',  # Tipo binario para archivos
            'datas': archivo_excel,  # Datos codificados en base64
            'store_fname': f'reporte_asistencia.xlsx',  # Nombre para almacenamiento
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # Tipo MIME correcto
        })
        # Retornar acción para descargar el archivo
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',  # URL para descarga
            'target': 'self'  # Abrir en la misma ventana
        }