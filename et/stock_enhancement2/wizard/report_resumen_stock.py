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
        worksheet_resumen = workbook.add_worksheet('RESUMEN DE STOCK')
        worksheet_entrada = workbook.add_worksheet('ENTRADA DE STOCK')
        worksheet_salida = workbook.add_worksheet('SALIDA DE STOCK')


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
        worksheet_entrada.merge_range(0, 0, 0, 7, ('REPORTE DE ENTRADA DE STOCK'), fmt_title)
        worksheet_entrada.set_column(0, 0, 20)      # Fecha
        worksheet_entrada.set_column(1, 1, 20)      # Codigo
        worksheet_entrada.set_column(2, 2, 70)      # Producto
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
        worksheet_salida.merge_range(0, 0, 0, 10, ('REPORTE DE SALIDA DE STOCK').upper(), fmt_title)
        worksheet_salida.set_column(0, 0, 20)      # Fecha
        worksheet_salida.set_column(1, 1, 20)      # Codigo
        worksheet_salida.set_column(2, 2, 70)      # Producto
        worksheet_salida.set_column(3, 3, 15)      # bulto
        worksheet_salida.set_column(4, 4, 10)      # UxB
        worksheet_salida.set_column(5, 5, 15)      # unidad
        worksheet_salida.set_column(6, 6, 20)      # Rubro
        worksheet_salida.set_column(7, 7, 40)      # Cliente
        worksheet_salida.set_column(8, 8, 60)      # Transferencia
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
        # ====== TITULO ======
        worksheet_resumen.merge_range(0, 0, 0, 8, 'REPORTE DE SALIDA DE STOCK', fmt_title)
        worksheet_resumen.set_row(0, 20)
        # ====== ANCHO DE COLUMNAS ======
        worksheet_resumen.set_column(0, 0, 20)  # CODIGO
        worksheet_resumen.set_column(1, 1, 70)  # PRODUCTO
        worksheet_resumen.set_column(2, 7, 15)  # columnas numéricas
        worksheet_resumen.set_column(8, 8, 40)  # ROTACIÓN
        # ====== ENCABEZADOS (2 filas) ======
        worksheet_resumen.set_row(1, 18)
        worksheet_resumen.set_row(2, 18)
        # Bloques verticales (2 filas)
        worksheet_resumen.merge_range(1, 0, 2, 0, 'CODIGO', fmt_header)
        worksheet_resumen.merge_range(1, 1, 2, 1, 'PRODUCTO', fmt_header)
        worksheet_resumen.merge_range(1, 8, 2, 8, 'ROTACIÓN', fmt_header)
        # Bloques horizontales (1ra fila de header)
        worksheet_resumen.merge_range(1, 2, 1, 4, 'ENTRADAS', fmt_header)
        worksheet_resumen.merge_range(1, 5, 1, 7, 'SALIDAS', fmt_header)
        # Sub-headers (2da fila de header)
        worksheet_resumen.write(2, 2, 'BULTOS', fmt_header)
        worksheet_resumen.write(2, 3, 'UxB', fmt_header)
        worksheet_resumen.write(2, 4, 'UNIDAD', fmt_header)
        worksheet_resumen.write(2, 5, 'BULTOS', fmt_header)
        worksheet_resumen.write(2, 6, 'UxB', fmt_header)
        worksheet_resumen.write(2, 7, 'UNIDAD', fmt_header)

        # =========================
        # DOMAIN
        # =========================
        domain = [('state', '=', 'done'), ('picking_type_id.code', '=', 'outgoing')]
        if self.temporada == 't_nino_2025':
            domain += [('create_date', '>=', date(2025, 3, 1)), ('create_date', '<=', date(2025, 8, 31))]
        elif self.temporada == 't_nav_2025':
            domain += [('create_date', '>=', date(2025, 9, 1)), ('create_date', '<=', date(2026, 2, 28))]
        _logger.info(f"Domain para busqueda de albaranes: {domain}")
        stock_pickings = self.env['stock.picking'].search(domain)
        _logger.info(f"Stock Pickings encontrados: {stock_pickings}")
        if not stock_pickings:
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
        row_resumen = 3
        resumen_data = {}
        # SALIDA DE STOCK
        for stock_picking in stock_pickings:
            for stock_move in stock_picking.move_lines:
                date_done = stock_picking.date_done.strftime('%d/%m/%Y') if stock_picking.date_done else ''
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
                        'bultos_entrada': 0.0,
                        'uxb_entrada': 0.0,
                        'unidad_entrada': 0.0,
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
                worksheet_salida.write(row_salida, 0, date_done, fmt_text2)
                worksheet_salida.write(row_salida, 1, stock_move.product_id.default_code or '', fmt_text2)
                worksheet_salida.write(row_salida, 2, stock_move.product_id.name or '', fmt_text)
                worksheet_salida.write_number(row_salida, 3, bultos, fmt_dec2)
                worksheet_salida.write_number(row_salida, 4, uxb, fmt_int)
                worksheet_salida.write_number(row_salida, 5, unidades, fmt_int)
                worksheet_salida.write(row_salida, 6, rubros_str or '', fmt_text2)
                worksheet_salida.write(row_salida, 7, stock_move.picking_id.partner_id.name or '', fmt_text)
                worksheet_salida.write(row_salida, 8, stock_move.picking_id.name, fmt_text)
                worksheet_salida.write(row_salida, 9, stock_move.picking_id.codigo_wms or '', fmt_text)
                worksheet_salida.write(row_salida, 10, stock_move.picking_id.company_id.name, fmt_text2)
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
                        'bultos_salida': 0.0,
                        'uxb_salida': 0.0,
                        'unidad_salida': 0.0,
                        'bultos_entrada': 0.0,
                        'uxb_entrada': 0.0,
                        'unidad_entrada': 0.0,
                    }
                unidades = move.quantity_send or 0.0
                uxb = move.uxb or None
                bultos = (unidades / uxb) if uxb else 0.0
                _logger.info(f"Procesando entrada - Producto: {move.product_id.name}, Unidades: {unidades}, UxB: {uxb}, Bultos: {bultos}")
                _logger.info(f"Antes de acumular - Resumen Data: {resumen_data[key]}")
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
            _logger.info(f"Resumen Data: {data}")
            if data['unidad_entrada'] == 0 or data['unidad_salida'] == 0:
                rotacion = 0.0
            else:
                rotacion = data['unidad_salida'] / data['unidad_entrada'] * 100.0 

            worksheet_resumen.write(row_resumen, 0, data['product_code'], fmt_text2)
            worksheet_resumen.write(row_resumen, 1, data['product_name'], fmt_text)
            #SALIDA DE STOCK
            worksheet_resumen.write_number(row_resumen, 2, data['bultos_salida'], fmt_dec2)
            worksheet_resumen.write_number(row_resumen, 3, data['uxb_salida'], fmt_int)
            worksheet_resumen.write_number(row_resumen, 4, data['unidad_salida'], fmt_int)
            # ENTRADA DE STOCK
            worksheet_resumen.write_number(row_resumen, 5, data['bultos_entrada'], fmt_dec2)
            worksheet_resumen.write_number(row_resumen, 6, data['uxb_entrada'], fmt_int)
            worksheet_resumen.write_number(row_resumen, 7, data['unidad_entrada'], fmt_int) 
            # Placeholder for rotation calculation
            worksheet_resumen.write_number(row_resumen, 8, rotacion, fmt_dec2)
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
        
