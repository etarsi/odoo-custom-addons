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
        worksheet.set_column(1, 1, 20)      # Doc. Origen
        worksheet.set_column(2, 2, 60)      # Cliente
        worksheet.set_column(3, 3, 15)      # Cantidad de Bultos
        worksheet.set_column(4, 4, 20)      # Total Facturado
        worksheet.set_column(5, 5, 20)      # Total N. Credito en Negativo
        worksheet.set_column(6, 6, 30)      # RUBROS (/)
        worksheet.set_column(7, 7, 15)      # Transferencia
        worksheet.set_column(8, 8, 40)      # Facturas (/)
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
        worksheet2.merge_range(0, 0, 0, 14, ('BASE DE DATOS').upper(), fmt_title)
        # =========================
        # COLUMNAS DE LA BASE DE DATOS
        # =========================
        worksheet2.set_column(0, 0, 12)  # CODIGO
        worksheet2.set_column(1, 1, 60)  # DESCRIPCION
        worksheet2.set_column(2, 2, 12)  # UNIDADES
        worksheet2.set_column(3, 3, 12)  # VALOR UNITARIO
        worksheet2.set_column(4, 4, 16)  # VALOR TOTAL
        worksheet2.set_column(5, 5, 12)  # UxB
        worksheet2.set_column(6, 6, 12)  # BULTOS
        worksheet2.set_column(7, 7, 12)  # Transferencia
        worksheet2.set_column(8, 8, 25)  # RUBRO
        worksheet2.set_column(9, 9, 25)  # CATEGORIA
        worksheet2.set_column(10, 10, 25)  # MARCA
        worksheet2.set_column(11, 11, 25)  # CONTRATO DISNEY
        worksheet2.set_column(12, 12, 25)  # SUBCONTRATO DISNEY
        worksheet2.set_column(13, 13, 25)  # PERSONAJE DISNEY
        worksheet2.set_column(14, 14, 25)  # PROPIEDAD DISNEY
        
        # Alto de filas de título/encabezado
        worksheet2.set_row(0, 20)
        worksheet2.set_row(1, 18)
        # =========================
        # ENCABEZADOS
        # =========================
        headers2 = ['CODIGO', 'DESCRIPCION', 'UNIDADES', 'VALOR UNITARIO', 'VALOR TOTAL', 'UxB', 'BULTOS', 'TRANSFERENCIA', 'RUBRO', 'CATEGORIA', 'MARCA', 'CONTRATO DISNEY', 'SUBCONTRATO DISNEY', 'PERSONAJE DISNEY', 'PROPIEDAD DISNEY']
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
                property_id, x_contract_id, x_subcontract_id, x_character_id = self.product_category_info(move.product_id)
                unidades = move.quantity_picked
                # UxB numérico: suele estar en el packaging.qty
                uxb = move.product_id.packaging_ids[0].qty if move.product_id.packaging_ids else 1
                #separar rubros por JUGUETES/ROPA/OTROS
                if move.product_id.categ_id.parent_id:
                    rubros.add(move.product_id.categ_id.parent_id.name)
                    rubros_str = '/'.join(rubros)   
                # BULTOS = unidades / UxB (como tu imagen)
                bultos = (unidades / uxb) if uxb else 0.0
                valor_unitario = move.transfer_id.sale_id.order_line.filtered(lambda l: l.product_id == move.product_id).price_unit if move.transfer_id and move.transfer_id.sale_id else 0.0
                descuento = move.transfer_id.sale_id.order_line.filtered(lambda l: l.product_id == move.product_id).discount if move.transfer_id and move.transfer_id.sale_id else 0.0
                valor_total = (unidades * valor_unitario) * (1 - descuento / 100) if valor_unitario else 0.0
                worksheet2.write(row2, 0, move.product_id.default_code or '', fmt_text2)
                worksheet2.write(row2, 1, move.product_id.name or '', fmt_text)
                worksheet2.write_number(row2, 2, unidades, fmt_int)
                worksheet2.write_number(row2, 3, valor_unitario, fmt_dec2)
                worksheet2.write_number(row2, 4, valor_total, fmt_dec2)
                worksheet2.write_number(row2, 5, uxb, fmt_int)
                worksheet2.write_number(row2, 6, bultos, fmt_dec2)
                worksheet2.write(row2, 7, wms_task.name, fmt_text)
                worksheet2.write(row2, 8, rubros_str or '', fmt_text2)
                worksheet2.write(row2, 9, (move.product_id.categ_id.name or '') if move.product_id.categ_id else '', fmt_text2)
                worksheet2.write(row2, 10, (move.product_id.product_brand_id.name or '') if move.product_id.product_brand_id else '', fmt_text2)
                worksheet2.write(row2, 11, x_contract_id.x_name if x_contract_id else '', fmt_text2)
                worksheet2.write(row2, 12, x_subcontract_id.x_name if x_subcontract_id else '', fmt_text2)
                worksheet2.write(row2, 13, x_character_id.x_name if x_character_id else '', fmt_text2)
                worksheet2.write(row2, 14, property_id.x_name if property_id else '', fmt_text2)
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
        
    def product_category_info(self, product):
        property_id = False
        x_contract_id = False
        x_subcontract_id = False
        x_character_id = False
        #buscamos si es producto con default code comienze con 9
        if product.default_code and product.default_code.startswith('9'):
            #buscamos en productos el mismo default code sin el 9 al inicio
            prod_con_propiedad = self.env['product.product'].search([('default_code', '=', product.default_code[1:])], limit=1)
            if prod_con_propiedad and prod_con_propiedad.x_property_id:
                property_id = prod_con_propiedad.x_property_id
                x_contract_id = prod_con_propiedad.x_contract_id
                x_subcontract_id = prod_con_propiedad.x_subcontract_id
                x_character_id = prod_con_propiedad.x_character_id
            else:
                property_id = False
                x_contract_id = False
                x_subcontract_id = False
                x_character_id = False
        else:
            property_id = product.x_property_id if product.x_property_id else False
            x_contract_id = product.x_contract_id if product.x_contract_id else False
            x_subcontract_id = product.x_subcontract_id if product.x_subcontract_id else False
            x_character_id = product.x_character_id if product.x_character_id else False
        
        return property_id, x_contract_id, x_subcontract_id, x_character_id