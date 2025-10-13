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
    
    # Generar el reporte en Excel
    def action_generar_excel(self):
        # Crear un buffer en memoria
        output = io.BytesIO()
        # Crear el archivo Excel
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Asistencias')
        # Agrupados por rangos consecutivos con mismo ancho
        worksheet.set_column(0, 0, 30)   # Empleado
        worksheet.set_column(1, 1, 20)   # Fecha Ingreso
        worksheet.set_column(2, 2, 20)   # Fecha Salida
        worksheet.set_column(3, 3, 10)   # Horas Trabajadas
        worksheet.set_column(4, 4, 10)   # Horas Extras
        worksheet.set_column(5, 5, 10)   # Horas Feriado
        worksheet.set_column(6, 6, 20)   # Tipo de Empleado
        worksheet.set_column(7, 7, 20)   # Turno Asignado
        
        #formato de celdas
        formato_encabezado = excel.formato_encabezado(workbook)
        formato_celdas_izquierda = excel.formato_celda_izquierda(workbook)
        formato_celdas_derecha = excel.formato_celda_derecha(workbook)
        formato_celdas_decimal = excel.formato_celda_decimal(workbook)
        fmt_emp = workbook.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'align': 'left'})
            
        # Escribir datos
        rango_start = self.date_start.strftime('%Y/%m/%d')
        rango_end = self.date_end.strftime('%Y/%m/%d')
        #colocar un titulo que diga SEBIGUS SRL en la primera fila centrado y en negrita de la a columna A a la E
        worksheet.merge_range(0, 0, 0, 7, 'SEBIGUS SRL', formato_encabezado)
        #colocar un subtitulo que diga REPORTE DE ASISTENCIA en la segunda fila centrado y en negrita de la a columna A a la E
        worksheet.merge_range(1, 0, 1, 7, 'REPORTE DE ASISTENCIA', formato_encabezado)
        #colocar un subtitulo que diga el rango de fechas en la tercera fila centrado y en negrita de la a columna A a la E
        worksheet.merge_range(2, 0, 2, 7, f'Rango de Fechas: {rango_start} a {rango_end}', formato_encabezado)
        # Escribir encabezados
        header_row = 4
        worksheet.write(header_row, 0, 'EMPLEADO', formato_encabezado)
        worksheet.write(header_row, 1, 'INGRESO', formato_encabezado)
        worksheet.write(header_row, 2, 'SALIDA', formato_encabezado)
        worksheet.write(header_row, 3, 'H. TRABAJADAS', formato_encabezado)
        worksheet.write(header_row, 4, 'H. 50%/EXTRA', formato_encabezado)
        worksheet.write(header_row, 5, 'H. 100%/FERIADOS/SABADOS', formato_encabezado)
        worksheet.write(header_row, 6, 'TIPO DE EMPLEADO', formato_encabezado)
        worksheet.write(header_row, 7, 'TURNO ASIGNADO', formato_encabezado)
        # Buscar facturas en el rango de fechas
        domain = [
            ('check_in', '>=', self.date_start),
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
        current_emp = False

        # --- 1) agrego una agregación por empleado para tener los totales ---
        groups = self.env['hr.attendance'].read_group(
            domain,
            ['employee_id', 'worked_hours:sum', 'overtime:sum', 'holiday_hours:sum'],
            ['employee_id'],
        )
        totales_por_emp = {
            g['employee_id'][0]: {
                'wh': g['worked_hours_sum'] or 0.0,
                'ot': g['overtime_sum'] or 0.0,
                'hh': g['holiday_hours_sum'] or 0.0,
            }
            for g in groups
        }

        for attendance in attendances:
            emp = attendance.employee_id
            # 2) cuando cambia de empleado, escribo la "cabecera" con los totales
            if not current_emp or emp.id != current_emp.id:
                tot = totales_por_emp.get(emp.id, {'wh': 0.0, 'ot': 0.0, 'hh': 0.0})
                # si no querés decimales en el rótulo, casteá a int:
                wh_total = int(round(tot['wh']))
                ot_total = int(round(tot['ot']))
                hh_total = int(round(tot['hh']))

                titulo = f"{emp.name}  |  T. Horas Trabajadas: {wh_total}  |  T. Horas al 50%: {ot_total}  |  T. Horas al 100%: {hh_total}"
                worksheet.merge_range(row, 0, row, 7, titulo, fmt_emp)
                row += 1
                current_emp = emp

            # Fechas formateadas
            ingreso = attendance.check_in.strftime('%d/%m/%Y %H:%M:%S') if attendance.check_in else ''
            salida = attendance.check_out.strftime('%d/%m/%Y %H:%M:%S') if attendance.check_out else ''
            tipo_empleado = 'Empleado' if attendance.employee_type == 'employee' else 'Eventual' if attendance.employee_type == 'eventual' else ''
            turno_asignado = 'Día' if attendance.employee_type_shift == 'day' else 'Noche' if attendance.employee_type_shift == 'night' else ''
            #como colocar una linea separacion entre empleados
            worksheet.write(row, 0, attendance.employee_id.name, formato_celdas_izquierda)
            worksheet.write(row, 1, ingreso, formato_celdas_derecha)
            worksheet.write(row, 2, salida, formato_celdas_derecha)
            worksheet.write(row, 3, attendance.worked_hours if attendance.worked_hours else 0, formato_celdas_derecha)
            worksheet.write(row, 4, attendance.overtime if attendance.overtime else 0, formato_celdas_derecha)
            worksheet.write(row, 5, attendance.holiday_hours if attendance.holiday_hours else 0, formato_celdas_derecha)
            worksheet.write(row, 6, tipo_empleado, formato_celdas_izquierda)
            worksheet.write(row, 7, turno_asignado, formato_celdas_izquierda)
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