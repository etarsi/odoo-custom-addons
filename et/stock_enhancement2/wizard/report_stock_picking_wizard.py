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

RUBROS = {
    'juguetes': 'JUGUETES',
    'maquillaje': 'MAQUILLAJE',
    'rodados': 'RODADOS',
    'pelotas': 'PELOTAS',
    'inflables': 'INFLABLES',
    'pistolas_agua': 'PISTOLAS DE AGUA',
    'vehiculos_bateria': 'VEHICULOS A BATERIA',
    'rodados_infantiles': 'RODADOS INFANTILES',
}

class ReportStockPickingWizard(models.TransientModel):
    _name = 'report.stock.picking.wizard'
    _description = 'Wizard para Exportar Facturas'

    temporada = fields.Selection(string='Temporada', selection=[
        ('t_nino_2025', 'Temporada Niño 2025'),
        ('t_nav_2025', 'Temporada Navidad 2025'),
    ], required=True, help='Seleccionar la temporada para el reporte')  
    partner_id = fields.Many2one('res.partner', string='Cliente', help='Seleccionar un Cliente para filtrar', required=True)
    rubro_select = fields.Selection(string='Rubro', selection=[('juguetes', 'JUGUETES'),
                                                            ('maquillaje', 'MAQUILLAJE'),
                                                            ('rodados', 'RODADOS'),
                                                            ('pelotas', 'PELOTAS'),
                                                            ('inflables', 'INFLABLES'),
                                                            ('pistolas_agua', 'PISTOLAS DE AGUA'),
                                                            ('vehiculos_bateria', 'VEHICULOS A BATERIA'),
                                                            ('rodados_infantiles', 'RODADOS INFANTILES')],
                                    required=True, default='juguetes', help='Seleccionar el rubro para el reporte')
    
    def action_generar_excel(self):
        # Crear un buffer en memoria
        output = io.BytesIO()
        # Crear el archivo Excel
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Inventario')
        # Agrupados por rangos consecutivos con mismo ancho
        worksheet.set_column(0, 0, 15)   # CODIGO
        worksheet.set_column(1, 1, 50)   # DESCRIPCION
        worksheet.set_column(2, 2, 20)   # UNIDADES
        worksheet.set_column(3, 3, 15)   # UXB
        worksheet.set_column(4, 4, 20)   # BULTOS
        worksheet.set_column(5, 5, 20)   # RUBRO
        worksheet.set_column(6, 6, 25)   # ESTADO
        
        #formato de celdas
        formato_encabezado = excel.formato_encabezado(workbook)
        formato_celdas_izquierda = excel.formato_celda_izquierda(workbook)
        formato_celdas_derecha = excel.formato_celda_derecha(workbook)
        formato_celdas_decimal = excel.formato_celda_decimal(workbook)
        # Escribir encabezados
        worksheet.merge_range('A1:G1', self.partner_id.name, formato_encabezado)
        
        worksheet.write(4, 0, 'CODIGO', formato_encabezado)
        worksheet.write(4, 1, 'DESCRIPCIÓN', formato_encabezado)
        worksheet.write(4, 2, 'UNIDADES', formato_encabezado)
        worksheet.write(4, 3, 'UxB', formato_encabezado)
        worksheet.write(4, 4, 'RUBRO', formato_encabezado)
        worksheet.write(4, 5, 'ESTADO', formato_encabezado)
        # Buscar facturas en el rango de fechas
        domain = [('state', '!=', 'cancel')]
        # Filtrar por temporada
        if self.temporada == 't_nino_2025':
            domain += [('create_date', '>=', date(2025, 3, 1)), ('invoice_date', '<=', date(2025, 8, 31))]
        elif self.temporada == 't_nav_2025':
            domain += [('create_date', '>=', date(2025, 9, 1)), ('invoice_date', '<=', date(2026, 2, 28))]
        # Filtrar por cliente si se seleccionó uno
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        # Recolectar los estados seleccionados en una lista
        stocks_pickings = self.env['stock.picking'].search(domain)
        # Escribir datos
        row = 5
        if not stocks_pickings:
            raise ValidationError("No se encontraron albaranes para los criterios seleccionados.")
        for stock_picking in stocks_pickings:
            pickings_moves = self.env['stock.move'].search([('picking_id', '=', stock_picking.id), ('product_id.categ_id.partner_id.name', '=', RUBROS.get(self.rubro_select, ''))])
            if pickings_moves:
                for move in pickings_moves:
                    # omitir movimientos sin producto
                    if not move.product_id:
                        continue
                    # omitir movimientos cerrados con albaranes hechos o cancelados
                    if move.state_wms == 'closed' and stock_picking.state in ['done', 'cancel']:
                        continue
                    # solo imprimir las lineas que tengan ese rubro
                    rubro_producto = move.product_id.categ_id.parent_id.name
                    if rubro_producto != self.rubro_select:
                        continue
                        
                    state = ''
                    if stock_picking.state_wms == 'closed' and stock_picking.state not in ['done', 'cancel']:
                        state = 'PREPARADO'
                    elif stock_picking.state_wms == 'no':
                        state = 'NO ENVIADO'
                    elif stock_picking.state_wms == 'done':
                        state = 'EN PREPARACIÓN'
                    
                    worksheet.write(row, 0, move.product_id.default_code if move.product_id.default_code else '', formato_celdas_izquierda)
                    worksheet.write(row, 1, move.product_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 2, move.product_uom_qty, formato_celdas_decimal)
                    worksheet.write(row, 3, move.product_packaging_id.name if move.product_packaging_id else '', formato_celdas_izquierda)
                    worksheet.write(row, 4, move.product_packaging_qty, formato_celdas_decimal)
                    worksheet.write(row, 5, state, formato_celdas_izquierda)
                    worksheet.write(row, 6, stock_picking.state.upper(), formato_celdas_izquierda)
                    row += 1
            else:
                continue
        workbook.close()
        output.seek(0)
        # Codificar el archivo en base64
        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'Pendientes {self.partner_id.name.lower()} - {fields.Date.today()}.xlsx',  # Nombre del archivo con fecha
            'type': 'binary',  # Tipo binario para archivos
            'datas': archivo_excel,  # Datos codificados en base64
            'store_fname': f'Pendientes {self.partner_id.name.lower()} - {fields.Date.today()}.xlsx',  # Nombre para almacenamiento
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # Tipo MIME correcto
        })
        # Retornar acción para descargar el archivo
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',  # URL para descarga
            'target': 'self'  # Abrir en la misma ventana
        }