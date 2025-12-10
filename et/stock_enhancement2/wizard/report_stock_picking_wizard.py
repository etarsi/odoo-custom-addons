from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter, logging
from . import excel
_logger = logging.getLogger(__name__)

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
    
    def action_generar_excel22(self):
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
            domain += [('create_date', '>=', date(2025, 3, 1)), ('create_date', '<=', date(2025, 8, 31))]
        elif self.temporada == 't_nav_2025':
            domain += [('create_date', '>=', date(2025, 9, 1)), ('create_date', '<=', date(2026, 2, 28))]
        # Filtrar por cliente si se seleccionó uno
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        # Recolectar los estados seleccionados en una lista
        stocks_pickings = self.env['stock.picking'].search(domain)
        # Escribir datos
        row = 3
        if not stocks_pickings:
            raise ValidationError("No se encontraron albaranes para los criterios seleccionados.")
        for stock_picking in stocks_pickings:
            pickings_moves = self.env['stock.move'].search([('picking_id', '=', stock_picking.id), ('product_id.categ_id.parent_id.name', '=', RUBROS.get(self.rubro_select, ''))])
            _logger.info(f"Procesando albarán {stock_picking.name} con {len(pickings_moves)} movimientos.")
            if pickings_moves:
                for move in pickings_moves:
                    # omitir movimientos sin producto
                    if not move.product_id:
                        continue
                    # omitir movimientos cerrados con albaranes hechos o cancelados
                    if stock_picking.state_wms == 'closed' and stock_picking.state in ['done', 'cancel']:
                        continue
                    row += 1
                    _logger.info(f"Escribiendo producto {move.product_id.name} en fila {row}.")
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
        
    def action_generar_excel(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Inventario')

        # =========================
        # FORMATOS (si no querés usar tu helper excel)
        # =========================
        fmt_title = workbook.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#000000',
            'align': 'center', 'valign': 'vcenter', 'border': 1
        })
        fmt_header = workbook.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#000000',
            'align': 'center', 'valign': 'vcenter', 'border': 1
        })
        fmt_text = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter'})
        fmt_int = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0'})
        fmt_dec2 = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0.00'})

        # =========================
        # COLUMNAS (como la imagen)
        # =========================
        worksheet.set_column(0, 0, 15)   # CODIGO
        worksheet.set_column(1, 1, 55)  # DESCRIPCION
        worksheet.set_column(2, 2, 12)  # UNIDADES
        worksheet.set_column(3, 3, 10)  # UxB
        worksheet.set_column(4, 4, 12)  # BULTOS
        worksheet.set_column(5, 5, 28)  # RUBRO
        worksheet.set_column(6, 6, 22)  # ESTADO

        # Alto de filas de título/encabezado
        worksheet.set_row(0, 20)
        worksheet.set_row(1, 18)

        # =========================
        # TITULO
        # =========================
        worksheet.merge_range(0, 0, 0, 6, (self.partner_id.name or '').upper(), fmt_title)

        # =========================
        # ENCABEZADOS
        # =========================
        headers = ['CODIGO', 'DESCRIPCION', 'UNIDADES', 'UxB', 'BULTOS', 'RUBRO', 'ESTADO']
        for col, h in enumerate(headers):
            worksheet.write(1, col, h, fmt_header)

        # =========================
        # DOMAIN
        # =========================
        domain = [('state', '!=', 'cancel')]

        if self.temporada == 't_nino_2025':
            domain += [('create_date', '>=', date(2025, 3, 1)), ('create_date', '<=', date(2025, 8, 31))]
        elif self.temporada == 't_nav_2025':
            domain += [('create_date', '>=', date(2025, 9, 1)), ('create_date', '<=', date(2026, 2, 28))]

        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))

        stocks_pickings = self.env['stock.picking'].search(domain)
        if not stocks_pickings:
            raise ValidationError("No se encontraron albaranes para los criterios seleccionados.")

        # =========================
        # DATA
        # =========================
        row = 2  # empezamos justo debajo de headers

        for stock_picking in stocks_pickings:
            pickings_moves = self.env['stock.move'].search([
                ('picking_id', '=', stock_picking.id),
                ('product_id.categ_id.parent_id.name', '=', RUBROS.get(self.rubro_select, ''))
            ])

            if not pickings_moves:
                continue

            # Estado WMS -> texto
            def _get_estado(p):
                if p.state_wms == 'closed' and p.state not in ['done', 'cancel']:
                    return 'PREPARADO'
                elif p.state_wms == 'no':
                    return 'NO ENVIADO'
                elif p.state_wms == 'done':
                    return 'EN PREPARACION'
                return ''

            estado_txt = _get_estado(stock_picking)

            for move in pickings_moves:
                if not move.product_id:
                    continue
                if stock_picking.state_wms == 'closed' and stock_picking.state in ['done', 'cancel']:
                    continue

                unidades = move.product_uom_qty or 0.0

                # UxB numérico: suele estar en el packaging.qty
                uxb = 0.0
                if move.product_packaging_id and hasattr(move.product_packaging_id, 'qty'):
                    uxb = move.product_packaging_id.qty or 0.0

                # BULTOS = unidades / UxB (como tu imagen)
                bultos = (unidades / uxb) if uxb else 0.0

                worksheet.write(row, 0, move.product_id.default_code or '', fmt_text)
                worksheet.write(row, 1, move.product_id.name or '', fmt_text)
                worksheet.write_number(row, 2, unidades, fmt_int)
                worksheet.write_number(row, 3, uxb, fmt_int)
                worksheet.write_number(row, 4, bultos, fmt_dec2)
                worksheet.write(row, 5, RUBROS.get(self.rubro_select, ''), fmt_text)
                worksheet.write(row, 6, estado_txt, fmt_text)

                row += 1

        workbook.close()
        output.seek(0)

        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'Pendientes {self.partner_id.name.lower()} - {fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': f'Pendientes {self.partner_id.name.lower()} - {fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self'
        }
