from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter, logging
from . import excel
_logger = logging.getLogger(__name__)


class ReportWmsTaskFacturaWizard(models.TransientModel):
    _name = 'report.wms.task.factura.wizard'
    _description = 'Wizard para Exportar Tareas y Facturas'

    temporada = fields.Selection(string='Temporada', selection=[
        ('t_all', 'Todas las Temporadas'),
        ('t_nino_2026', 'Temporada Niño 2026'),
    ], required=True, default='t_nino_2026', help='Seleccionar la temporada para el reporte')  
    partner_ids = fields.Many2many('res.partner', string='Clientes', help='Seleccionar un Cliente para filtrar')
    category_ids = fields.Many2many('product.category', string='Categorías de Producto', help='Filtrar por categorías de producto', domain=[('parent_id', '=', False)])
    company_ids = fields.Many2many('res.company', string='Compañías', help='Filtrar por Compañías')
    type_picking = fields.Selection(string='Tipo de Transferencia', selection=[
        ('inputs', 'Insumos'),
        ('order', 'Pedidos'),
        ('return', 'Devoluciones'),
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
        worksheet.merge_range(0, 0, 0, 11, ('REPORTE DE TAREAS-FACTURAS REALIZADAS'), fmt_title)
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
        worksheet.set_column(7, 7, 55)      # Transferencia
        worksheet.set_column(8, 8, 30)      # Facturas (/)
        worksheet.set_column(9, 9, 15)      # Cant. LINEA DE PEDIDOS
        # Alto de filas de título/encabezado
        worksheet.set_row(0, 20)
        worksheet.set_row(1, 18)
        # =========================
        # ENCABEZADOS
        # =========================
        headers = ['FECHA', 'DOC. ORIGEN', 'CLIENTE', 'CANT. BULTOS', 'T. FACTURADO', 'T. N. CRÉDITO', 'RUBROS', 'TRANSFERENCIA', 'FACTURAS', 'L. PEDIDOS']
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
        domain = [('digip_state', '=', 'remitido')]
        if self.temporada != 't_all':
            if self.temporada == 't_nino_2026':
                domain += [('create_date', '>=', date(2026, 1, 1)), ('create_date', '<=', date(2026, 8, 31))]
        
        if self.partner_ids:
            domain += [('partner_id', 'in', self.partner_ids.ids)]
        if self.type_picking == 'inputs':
            domain += [('transfer_id.operation_type', '=', 'incoming')]
        elif self.type_picking == 'order':
            domain += [('transfer_id.operation_type', '=', 'outgoing')]

        wms_tasks = self.env['wms.task'].search(domain)
        if not wms_tasks:
            raise ValidationError("No se encontraron albaranes para los criterios seleccionados.")

        # =========================
        # DATA
        # =========================
        row = 2  # empezamos justo debajo de headers
        row2 = 2  # empezamos justo debajo de headers de hoja BASE DE DATOS
        if self.category_ids:
            #filtrar por las category_ids seleccionadas
            wms_tasks = wms_tasks.filtered(lambda sp: not sp.task_line_ids.filtered(lambda m: m.product_id.categ_id.parent_id not in self.category_ids or m.product_id.categ_id not in self.category_ids))
        for wms_task in wms_tasks:
            date_done = wms_task.date_done.strftime('%d/%m/%Y') if wms_task.date_done else ''
            t_facturado = 0.0
            t_ncredito = 0.0
            t_cant_bultos = 0.0
            rubros = set()
            facturas = set()
            rubros_str = ''
            facturas_str = ''
            t_cant_lineas = len(wms_task.task_line_ids)
            
            invoice_ids = wms_task.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
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
            for move in wms_task.task_line_ids:
                if not move.product_id:
                    continue
                unidades = move.quantity_picked
                # UxB numérico: suele estar en el packaging.qty
                uxb = move.product_id.product_packaging_ids[0].qty if move.product_id.product_packaging_ids else 1
                #separar rubros por JUGUETES/ROPA/OTROS
                if move.product_id.categ_id.parent_id:
                    rubros.add(move.product_id.categ_id.parent_id.name)
                    rubros_str = '/'.join(rubros)   
                # BULTOS = unidades / UxB (como tu imagen)
                bultos = (unidades / uxb) if uxb else 0.0
                worksheet2.write(row2, 0, move.product_id.default_code or '', fmt_text2)
                worksheet2.write(row2, 1, move.product_id.name or '', fmt_text)
                worksheet2.write_number(row2, 2, unidades, fmt_int)
                worksheet2.write_number(row2, 3, uxb, fmt_int)
                worksheet2.write_number(row2, 4, bultos, fmt_dec2)
                worksheet2.write(row2, 5, rubros_str or '', fmt_text2)
                worksheet2.write(row2, 6, wms_task.name, fmt_text)
                row2 += 1
                t_cant_bultos += bultos
            
            t_cant_bultos = float_round(t_cant_bultos, 2)
            #Sacar el nombre del cliente si tiene 
            partner = wms_task.partner_id
            if partner:
                parent_name = partner.parent_id.name or ""
                child_name = partner.name or ""
                if partner.company_type == "person" and parent_name:
                    partner_name = f"{parent_name} / {child_name}"
                else:
                    partner_name = child_name
            else:
                partner_name = ""

            #DATOS DE LAS FILAS DE REPORTE ENTREGA
            worksheet.write(row, 0, date_done, fmt_text2)
            worksheet.write(row, 1, wms_task.transfer_id.origin, fmt_text)
            worksheet.write(row, 2, partner_name or '', fmt_text)
            worksheet.write(row, 3, t_cant_bultos, fmt_text2)
            worksheet.write(row, 4, t_facturado, fmt_moneda)
            worksheet.write(row, 5, t_ncredito, fmt_moneda)
            worksheet.write(row, 6, rubros_str, fmt_text2)
            worksheet.write(row, 7, wms_task.name, fmt_text)
            worksheet.write(row, 8, facturas_str, fmt_text2)
            worksheet.write(row, 9, t_cant_lineas, fmt_int)
            row += 1
        workbook.close()
        output.seek(0)

        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'Reporte Tareas/Factura - {fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': f'Reporte Tareas/Factura - {fields.Date.today()}.xlsx',
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