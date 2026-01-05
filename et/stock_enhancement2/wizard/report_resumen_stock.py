from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter, logging
from . import excel
_logger = logging.getLogger(__name__)


class ReportResumenStockWizard(models.TransientModel):
    _name = 'report.resumen.stock.wizard'
    _description = 'Wizard para generar Resumen de Stock'

    temporada = fields.Selection(string='Temporada', selection=[
        ('t_all', 'Todas las Temporadas'),
        ('t_nino_2025', 'Temporada Niño 2025'),
        ('t_nav_2025', 'Temporada Navidad 2025'),
        ('t_nino_2026', 'Temporada Niño 2026'),
    ], required=True, default='t_nav_2025', help='Seleccionar la temporada para el reporte')  
    type_picking = fields.Selection(string='Tipo de Transferencia', selection=[
        ('inputs', 'Insumos'),
        ('order', 'Pedidos'),
        ('all', 'Todos'),
    ], help='Seleccionar el tipo de transferencia para el reporte', default='order', required=True)
    


    def action_generar_excel(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet_entrada = workbook.add_worksheet('ENTRADA DE STOCK')
        worksheet_salida = workbook.add_worksheet('SALIDA DE STOCK')
        worksheet_resumen = workbook.add_worksheet('RESUMEN DE STOCK')

        # =========================
        # FORMATOS
        # =========================
        fmt_title = workbook.add_format({
            'bold': True,
            'font_color': '#FFFFFF',
            'bg_color': '#000000',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#FFFFFF',
        })

        fmt_header = workbook.add_format({
            'bold': True,
            'font_color': '#FFFFFF',
            'bg_color': '#000000',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#FFFFFF',
        })
        fmt_text = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter'})
        fmt_text2 = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        fmt_moneda = workbook.add_format({'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '$#,##0.00'})
        fmt_int = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0'})
        fmt_dec2 = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0.00'})


        # =========================
        # HOJA ENTRADA DE STOCK
        # =========================
        worksheet_entrada.merge_range(0, 0, 0, 11, ('REPORTE DE ENTRADA DE STOCK'), fmt_title)
        worksheet_entrada.set_column(0, 0, 20)      # Fecha
        worksheet_entrada.set_column(1, 1, 20)      # Codigo
        worksheet_entrada.set_column(2, 2, 60)      # Producto
        worksheet_entrada.set_column(3, 3, 15)      # bulto
        worksheet_entrada.set_column(4, 4, 10)      # UxB
        worksheet_entrada.set_column(5, 5, 15)      # unidad
        worksheet_entrada.set_column(6, 6, 30)      # contenedor
        worksheet_entrada.set_column(7, 7, 30)      # Licencia
        # Alto de filas de título/encabezado
        worksheet_entrada.set_row(0, 20)
        worksheet_entrada.set_row(1, 18)
        # =========================
        # ENCABEZADOS
        # =========================
        headers = ['FECHA', 'CODIGO', 'DESCRIPCIÓN', 'BULTO', 'UxB', 'UNIDAD', 'CONTENEDOR', 'LICENCIA']
        for col, h in enumerate(headers):
            worksheet_entrada.write(1, col, h, fmt_header)


        # =========================
        # HOJA SALIDA DE STOCK
        # =========================
        worksheet_salida.merge_range(0, 0, 0, 6, ('REPORTE DE SALIDA DE STOCK').upper(), fmt_title)
        worksheet_salida.set_column(0, 0, 20)      # Fecha
        worksheet_salida.set_column(1, 1, 20)      # Codigo
        worksheet_salida.set_column(2, 2, 60)      # Producto
        worksheet_salida.set_column(3, 3, 15)      # bulto
        worksheet_salida.set_column(4, 4, 10)      # UxB
        worksheet_salida.set_column(5, 5, 15)      # unidad
        worksheet_salida.set_column(6, 6, 30)      # Rubro
        worksheet_salida.set_column(7, 7, 30)      # Cliente
        worksheet_salida.set_column(8, 8, 30)      # Transferencia
        worksheet_salida.set_column(9, 9, 15)      # Codigo WMS
        worksheet_salida.set_column(10, 10, 30)    # Compañia
        # Alto de filas de título/encabezado
        worksheet_salida.set_row(0, 20)
        worksheet_salida.set_row(1, 18)
        # =========================
        # ENCABEZADOS
        # =========================
        headers_salida = ['FECHA', 'CODIGO', 'DESCRIPCIÓN', 'BULTO', 'UxB', 'UNIDAD', 'RUBRO', 'CLIENTE', 'TRANSFERENCIA', 'CÓDIGO WMS', 'COMPAÑIA']
        for col, h in enumerate(headers_salida):
            worksheet_salida.write(1, col, h, fmt_header)
            
        # =========================
        # HOJA RESUMEN DE STOCK
        # =========================
        worksheet_resumen.merge_range(0, 0, 0, 6, ('REPORTE RESUMEN DE STOCK').upper(), fmt_title)
        worksheet_resumen.set_column(0, 0, 20)      # Codigo
        worksheet_resumen.set_column(1, 1, 20)      # Descroipción
        worksheet_resumen.set_column(2, 2, 60)      # Bulto 
        worksheet_resumen.set_column(3, 3, 15)      # UxB
        worksheet_resumen.set_column(4, 4, 10)      # Unidad
        worksheet_resumen.set_column(2, 2, 60)      # Bulto 
        worksheet_resumen.set_column(3, 3, 15)      # UxB
        worksheet_resumen.set_column(5, 5, 15)      # unidad
        worksheet_resumen.set_column(6, 6, 30)      # Rotacion
        # Alto de filas de título/encabezado
        worksheet_resumen.set_row(0, 20)
        worksheet_resumen.set_row(1, 18)
        # =========================
        # ENCABEZADOS
        # =========================
        headers_resumen = ['CODIGO', 'DESCRIPCIÓN', 'BULTO', 'UxB', 'UNIDAD', 'BULTO', 'UxB', 'UNIDAD', 'ROTACIÓN']
        for col, h in enumerate(headers_resumen):
            worksheet_resumen.write(1, col, h, fmt_header)

        # =========================
        # DOMAIN
        # =========================
        domain = [('state', '=', 'done')]
        if self.temporada == 't_nino_2025':
            domain += [('picking_id.create_date', '>=', date(2025, 3, 1)), ('picking_id.create_date', '<=', date(2025, 8, 31))]
        elif self.temporada == 't_nav_2025':
            domain += [('picking_id.create_date', '>=', date(2025, 9, 1)), ('picking_id.create_date', '<=', date(2026, 2, 28))]
        domain += [('picking_type_id.code', '=', 'incoming')]
        stock_moves = self.env['stock.move'].search(domain)
        if not stock_moves:
            raise ValidationError("No se encontraron albaranes para los criterios seleccionados.")
        
        domain_container = [('state', '=', 'confirmed')]
        if self.temporada == 't_nino_2025':
            domain_container += [('eta', '>=', date(2025, 3, 1)), ('eta', '<=', date(2025, 8, 31))]
        elif self.temporada == 't_nav_2025':
            domain_container += [('eta', '>=', date(2025, 9, 1)), ('eta', '<=', date(2026, 2, 28))] 

        containers = self.env['container'].search(domain_container)
        # =========================
        # DATA
        # =========================
        row_entrada = 2
        row_salida = 2
        row_resumen = 2
        resumen_data = {}
        # SALIDA DE STOCK
        for stock_move in stock_moves:
            date_done = stock_move.picking_id.date_done.strftime('%d/%m/%Y') if stock_move.picking_id.date_done else ''
            rubros = set()
            rubros_str = ''
            if not stock_move.product_id:
                continue
            key = stock_move.product_id.id
            if key not in resumen_data:
                resumen_data[key] = {
                    'product_code': stock_move.product_id.default_code or '', 
                    'product_name': stock_move.product_id.name or '',
                    'bultos_salida': 0.0,
                    'uxb_salida': 0.0,
                    'unidad_salida': 0.0,
                    'rotacion': 0.0,
                }
            unidades = stock_move.product_uom_qty or 0.0
            uxb = 0.0
            if stock_move.product_packaging_id and hasattr(stock_move.product_packaging_id, 'qty'):
                uxb = stock_move.product_packaging_id.qty or 0.0
            bultos = (unidades / uxb) if uxb else 0.0
            resumen_data[key]['bultos_salida'] += bultos
            resumen_data[key]['uxb_salida'] = uxb  # assuming UxB is consistent per product
            resumen_data[key]['unidad_salida'] += unidades
            if stock_move.product_packaging_id and hasattr(stock_move.product_packaging_id, 'qty'):
                 stock_move.product_packaging_qty
            #separar rubros por JUGUETES/ROPA/OTROS
            if stock_move.product_id.categ_id.parent_id:
                rubros.add(stock_move.product_id.categ_id.parent_id.name)
                rubros_str = '/'.join(rubros)   
            unidades = stock_move.product_uom_qty or 0.0
            # UxB numérico: suele estar en el packaging.qty
            uxb = 0.0
            if stock_move.product_packaging_id and hasattr(stock_move.product_packaging_id, 'qty'):
                uxb = stock_move.product_packaging_id.qty or 0.0
            # BULTOS = unidades / UxB (como tu imagen)
            bultos = (unidades / uxb) if uxb else 0.0
            worksheet_salida.write(row_salida, 0, stock_move.product_id.default_code or '', fmt_text2)
            worksheet_salida.write(row_salida, 1, stock_move.product_id.name or '', fmt_text)
            worksheet_salida.write_number(row_salida, 2, unidades, fmt_int)
            worksheet_salida.write_number(row_salida, 3, uxb, fmt_int)
            worksheet_salida.write_number(row_salida, 4, bultos, fmt_dec2)
            worksheet_salida.write(row_salida, 5, rubros_str or '', fmt_text2)
            worksheet_salida.write(row_salida, 6, stock_move.picking_id.partner_id.name or '', fmt_text)
            worksheet_salida.write(row_salida, 6, stock_move.picking_id.name, fmt_text)
            worksheet_salida.write(row_salida, 7, stock_move.picking_id.codigo_wms or '', fmt_text)
            worksheet_salida.write(row_salida, 8, stock_move.picking_id.company_id.name, fmt_text2)
            row_salida += 1
        
        #Entrada de STOCK
        for container in containers:
            for move in container.lines:
                if not move.product_id:
                    continue
                key = move.product_id.id
                if key not in resumen_data:
                    resumen_data[key] = {
                        'product_code': move.product_id.default_code or '',
                        'product_name': move.product_id.name or '',
                        'bultos_entrada': 0.0,
                        'uxb_entrada': 0.0,
                        'unidad_entrada': 0.0,
                        'rotacion': 0.0,
                    }
                unidades = move.quantity_send or 0.0
                uxb = move.uxb or 0.0
                bultos = (unidades / uxb) if uxb else 0.0
                resumen_data[key]['bultos_entrada'] += bultos
                resumen_data[key]['uxb_entrada'] = uxb  # assuming UxB is consistent per product
                resumen_data[key]['unidad_entrada'] += unidades
                
                date_done = container.eta.strftime('%d/%m/%Y') if container.eta else ''
                worksheet_entrada.write(row_entrada, 0, date_done, fmt_text2)
                worksheet_entrada.write(row_entrada, 1, move.product_id.default_code or '', fmt_text2)
                worksheet_entrada.write(row_entrada, 2, move.product_id.name or '', fmt_text)
                worksheet_entrada.write_number(row_entrada, 3, move.bultos or 0.0,  fmt_dec2)
                worksheet_entrada.write_number(row_entrada, 4, move.uxb, fmt_int)
                worksheet_entrada.write_number(row_entrada, 5, move.quantity_send or 0.0, fmt_int)
                worksheet_entrada.write(row_entrada, 6, container.name or '', fmt_text)
                worksheet_entrada.write(row_entrada, 7, container.license or '', fmt_text)
                row_entrada += 1
                
        entrada_counters = {}
        for container in containers:
            for move in container.lines:
                if not move.product_id:
                    continue
                key = move.product_id.id
                if key not in entrada_counters:
                    entrada_counters[key] = 0.0
                unidades = move.quantity_send or 0.0
                entrada_counters[key] += unidades
        # RESUMEN DE STOCK
        for data in resumen_data.values():
            rotacion = data['unidad_salida'] / data['unidad_entrada'] * 100.0 
            worksheet_resumen.write(row_resumen, 0, data['product_code'], fmt_text2)
            worksheet_resumen.write(row_resumen, 1, data['product_name'], fmt_text)
            #SALIDA DE STOCK
            worksheet_resumen.write_number(row_resumen, 2, data['bultos_salida'], fmt_dec2)
            worksheet_resumen.write_number(row_resumen, 3, data['uxb_salida'], fmt_int)
            worksheet_resumen.write_number(row_resumen, 4, data['unidad_salida'], fmt_int)
            # ENTRADA DE STOCK
            worksheet_resumen.write_number(row_resumen, 2, data['bultos_entrada'], fmt_dec2)
            worksheet_resumen.write_number(row_resumen, 3, data['uxb_entrada'], fmt_int)
            worksheet_resumen.write_number(row_resumen, 4, data['unidad_entrada'], fmt_int) 
            # Placeholder for rotation calculation
            worksheet_resumen.write_number(row_resumen, 5, rotacion, fmt_dec2)
            row_resumen += 1
        workbook.close()
        output.seek(0)
        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'Reporte Resumen de Stock - {fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': f'Reporte Resumen de Stock - {fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Éxito',
                'message': 'Excel generado correctamente.',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/{attachment.id}?download=true',
                    'target': 'self',
                }
            }
        }
        
