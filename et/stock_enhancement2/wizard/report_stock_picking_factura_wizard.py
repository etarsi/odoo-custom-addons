from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter, logging
from . import excel
_logger = logging.getLogger(__name__)


class ReportStockPickingFacturaWizard(models.TransientModel):
    _name = 'report.stock.picking.factura.wizard'
    _description = 'Wizard para Exportar Transferencias y Facturas'

    temporada = fields.Selection(string='Temporada', selection=[
        ('t_all', 'Todas las Temporadas'),
        ('t_nino_2025', 'Temporada Niño 2025'),
        ('t_nav_2025', 'Temporada Navidad 2025'),
    ], required=True, default='t_nav_2025', help='Seleccionar la temporada para el reporte')  
    partner_ids = fields.Many2many('res.partner', string='Clientes', help='Seleccionar un Cliente para filtrar')
    category_ids = fields.Many2many('product.category', string='Categorías de Producto', help='Filtrar por categorías de producto', domain=[('parent_id', '=', False)])
    company_ids = fields.Many2many('res.company', string='Compañías', help='Filtrar por Compañías')
    type_picking = fields.Selection(string='Tipo de Transferencia', selection=[
        ('inputs', 'Insumos'),
        ('order', 'Pedidos'),
        ('all', 'Todos'),
    ], help='Seleccionar el tipo de transferencia para el reporte', default='order', required=True)
    


    def action_generar_excel(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('REPORTE ENTREGA')
        worksheet2 = workbook.add_worksheet('BASE DE DATOS')

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
        # TITULO
        # =========================
        worksheet.merge_range(0, 0, 0, 11, ('REPORTE DE TRANSFERENCIAS-FACTURAS REALIZADAS'), fmt_title)
        # =========================
        # COLUMNAS DE LA HOJA REPORTE DE ENTREGA
        # =========================
        worksheet.set_column(0, 0, 15)      # Fecha
        worksheet.set_column(1, 1, 30)      # Doc. Origen
        worksheet.set_column(2, 2, 60)      # Cliente
        worksheet.set_column(3, 3, 15)      # Cantidad de Bultos
        worksheet.set_column(4, 4, 20)      # Total Facturado
        worksheet.set_column(5, 5, 20)      # Total N. Credito en Negativo
        worksheet.set_column(6, 6, 30)      # RUBROS (/)
        worksheet.set_column(7, 7, 20)      # COMPAÑIA
        worksheet.set_column(8, 8, 55)      # Transferencia
        worksheet.set_column(9, 9, 15)      # Código WMS
        worksheet.set_column(10, 10, 30)     # Facturas (/)
        worksheet.set_column(11, 11, 15)    # Cant. LINEA DE PEDIDOS
        # Alto de filas de título/encabezado
        worksheet.set_row(0, 20)
        worksheet.set_row(1, 18)
        # =========================
        # ENCABEZADOS
        # =========================
        headers = ['FECHA', 'DOC. ORIGEN', 'CLIENTE', 'CANT. BULTOS', 'T. FACTURADO', 'T. N. CRÉDITO', 'RUBROS', 'COMPAÑÍA', 'TRANSFERENCIA', 'CÓDIGO WMS', 'FACTURAS', 'L. PEDIDOS']
        for col, h in enumerate(headers):
            worksheet.write(1, col, h, fmt_header)


        # =========================
        # TITULO
        # =========================
        worksheet2.merge_range(0, 0, 0, 6, ('BASE DE DATOS').upper(), fmt_title)
        # =========================
        # COLUMNAS DE LA BASE DE DATOS
        # =========================
        worksheet2.set_column(0, 0, 12)  # CODIGO
        worksheet2.set_column(1, 1, 60)  # DESCRIPCION
        worksheet2.set_column(2, 2, 12)  # UNIDADES
        worksheet2.set_column(3, 3, 10)  # UxB
        worksheet2.set_column(4, 4, 12)  # BULTOS
        worksheet2.set_column(5, 5, 28)  # RUBRO
        worksheet2.set_column(6, 6, 60)  # Transferencia
        # Alto de filas de título/encabezado
        worksheet2.set_row(0, 20)
        worksheet2.set_row(1, 18)
        # =========================
        # ENCABEZADOS
        # =========================
        headers2 = ['CODIGO', 'DESCRIPCION', 'UNIDADES', 'UxB', 'BULTOS', 'RUBRO', 'TRANSFERENCIA']
        for col, h in enumerate(headers2):
            worksheet2.write(1, col, h, fmt_header)
            
            
            
        # =========================
        # DOMAIN
        # =========================
        domain = [('state', '=', 'done')]
        if self.temporada != 't_all':
            if self.temporada == 't_nino_2025':
                domain += [('create_date', '>=', date(2025, 3, 1)), ('create_date', '<=', date(2025, 8, 31))]
            elif self.temporada == 't_nav_2025':
                domain += [('create_date', '>=', date(2025, 9, 1)), ('create_date', '<=', date(2026, 2, 28))]
        
        if self.partner_ids:
            domain += [('partner_id', 'in', self.partner_ids.ids)]
        if self.type_picking == 'inputs':
            domain += [('picking_type_id.code', '=', 'incoming')]
        elif self.type_picking == 'order':
            domain += [('picking_type_id.code', '=', 'outgoing')]

        stocks_pickings = self.env['stock.picking'].search(domain)
        if not stocks_pickings:
            raise ValidationError("No se encontraron albaranes para los criterios seleccionados.")

        # =========================
        # DATA
        # =========================
        row = 2  # empezamos justo debajo de headers
        row2 = 2  # empezamos justo debajo de headers de hoja BASE DE DATOS
        if self.category_ids:
            #filtrar por las category_ids seleccionadas
            stocks_pickings = stocks_pickings.filtered(lambda sp: not sp.move_ids_without_package.filtered(lambda m: m.product_id.categ_id.parent_id not in self.category_ids))
        for stock_picking in stocks_pickings:
            
            if self.category_ids and stock_picking.move_ids_without_package.filtered(lambda m: m.product_id.categ_id.parent_id not in self.category_ids):
                continue
            date_done = stock_picking.date_done.strftime('%d/%m/%Y') if stock_picking.date_done else ''
            t_facturado = 0.0
            t_ncredito = 0.0
            t_cant_bultos = 0.0
            rubros = set()
            facturas = set()
            rubros_str = ''
            facturas_str = ''
            t_cant_lineas = len(stock_picking.move_lines)
            
            invoice_ids = stock_picking.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
            if invoice_ids:
                for invoice in invoice_ids:
                    if invoice.move_type == 'out_invoice':
                        facturas.add(invoice.name)
                        t_facturado += invoice.amount_total
                    elif invoice.move_type == 'out_refund':
                        facturas.add(invoice.name)
                        t_ncredito += invoice.amount_total            
                #t_ncredito sea negativo
                facturas_str = '/'.join(facturas)
                if t_ncredito > 0:
                    t_ncredito = -abs(t_ncredito)
            
            domain_moves = [('picking_id', '=', stock_picking.id)]
            if self.category_ids:
                domain_moves += [('product_id.categ_id.parent_id', 'in', self.category_ids.ids)]
            else:
                domain_moves += [('product_id.categ_id.parent_id', '!=', False)]
            # Buscar los movimientos de stock asociados al albarán
            pickings_moves = self.env['stock.move'].search(domain_moves)
            if not pickings_moves:
                continue

            for move in pickings_moves:
                if not move.product_id:
                    continue
                t_cant_bultos += move.product_packaging_qty
                unidades = move.product_uom_qty or 0.0
                # UxB numérico: suele estar en el packaging.qty
                uxb = 0.0
                if move.product_packaging_id and hasattr(move.product_packaging_id, 'qty'):
                    t_cant_bultos += move.product_packaging_qty
                #separar rubros por JUGUETES/ROPA/OTROS
                if move.product_id.categ_id.parent_id:
                    rubros.add(move.product_id.categ_id.parent_id.name)
                    rubros_str = '/'.join(rubros)   
                # BULTOS = unidades / UxB (como tu imagen)
                bultos = (unidades / uxb) if uxb else 0.0
                unidades = move.product_uom_qty or 0.0
                # UxB numérico: suele estar en el packaging.qty
                uxb = 0.0
                if move.product_packaging_id and hasattr(move.product_packaging_id, 'qty'):
                    uxb = move.product_packaging_id.qty or 0.0
                # BULTOS = unidades / UxB (como tu imagen)
                bultos = (unidades / uxb) if uxb else 0.0
                worksheet2.write(row2, 0, move.product_id.default_code or '', fmt_text2)
                worksheet2.write(row2, 1, move.product_id.name or '', fmt_text)
                worksheet2.write_number(row2, 2, unidades, fmt_int)
                worksheet2.write_number(row2, 3, uxb, fmt_int)
                worksheet2.write_number(row2, 4, bultos, fmt_dec2)
                worksheet2.write(row2, 5, rubros_str or '', fmt_text2)
                worksheet2.write(row2, 6, stock_picking.name, fmt_text)
                row2 += 1
            
            t_cant_bultos = float_round(t_cant_bultos, 2)
            #Sacar el nombre del cliente si tiene 
            partner_name = (stock_picking.partner_id.parent_id.name) + ' / ' + stock_picking.partner_id.name if stock_picking.partner_id.company_type== 'person' else stock_picking.partner_id.name if stock_picking.partner_id else ''
            #DATOS DE LAS FILAS DE REPORTE ENTREGA
            worksheet.write(row, 0, date_done, fmt_text2)
            worksheet.write(row, 1, stock_picking.origin, fmt_text)
            worksheet.write(row, 2, partner_name or '', fmt_text)
            worksheet.write(row, 3, t_cant_bultos, fmt_text2)
            worksheet.write(row, 4, t_facturado, fmt_moneda)
            worksheet.write(row, 5, t_ncredito, fmt_moneda)
            worksheet.write(row, 6, rubros_str, fmt_text2)
            worksheet.write(row, 7, stock_picking.company_id.name, fmt_text2)
            worksheet.write(row, 8, stock_picking.name, fmt_text)
            worksheet.write(row, 9, stock_picking.codigo_wms, fmt_text)
            worksheet.write(row, 10, facturas_str, fmt_text2)
            worksheet.write(row, 11, t_cant_lineas, fmt_int)
            row += 1
        workbook.close()
        output.seek(0)

        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'Reporte Transferencias/Factura - {fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': f'Reporte Transferencias/Factura - {fields.Date.today()}.xlsx',
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