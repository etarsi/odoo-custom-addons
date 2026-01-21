from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter, logging
from . import excel
_logger = logging.getLogger(__name__)


class ReportStockValorizadoWizard(models.TransientModel):
    _name = 'report.stock.valorizado.wizard'
    _description = 'Wizard para Reporte de Stock Valorizado'
    
    #lista de precios
    price_list_id = fields.Many2one('product.pricelist', string='Lista de Precios', help='Seleccionar una Lista de Precios para valorizar el stock')
    


    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        self.parent_ids = False
        if self.partner_id:
            parent_ids = self.env['res.partner'].search([('parent_id', '=', self.partner_id.id)])
            if parent_ids:
                self.parent_ids = parent_ids
            else:
                self.parent_ids = False
            return {'domain': {'parent_ids': [('parent_id', '=', self.partner_id.id)]}}

    def action_generar_excel(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Valorización de Stock')

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
        fmt_int = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0'})
        fmt_dec = workbook.add_format({'border': 1, 'align': 'center', '', 'valign': 'vcenter', 'num_format': '0.00'})
        fmt_dec2 = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '"$" #,##0.00'})
        rm_dec2 = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'num_format': '"$" #,##0.00'})
        rm_text = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'blold': True})
        #formato contabilidad
        fcont_dec = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'})
        fcont_dec2 = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'num_format': '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'})

        # =========================
        # COLUMNAS
        # =========================
        worksheet.set_column(0, 0, 15)  # CODIGO
        worksheet.set_column(1, 1, 60)  # DESCRIPCION
        worksheet.set_column(2, 2, 25)  # MARCA
        worksheet.set_column(3, 3, 25)  # RUBRO
        worksheet.set_column(4, 4, 12)  # UNIDADES
        worksheet.set_column(5, 5, 12)  # UxB
        worksheet.set_column(6, 6, 12)  # BULTOS
        worksheet.set_column(7, 7, 20)  # PRECIO DE LISTA
        worksheet.set_column(8, 8, 20)  # VALOR
        

        # Alto de filas de título/encabezado
        worksheet.set_row(0, 20)
        worksheet.set_row(1, 18)
        # =========================
        # TITULO
        # =========================
        worksheet.merge_range(0, 0, 0, 8, 'REPORTE DE VALORIZACIÓN', fmt_title)
        #RESUMEN
        worksheet.merge_range(1, 0, 1, 8, 'RESUMEN', fmt_title)
        #DETALLE
        worksheet.merge_range(7, 0, 7, 8, 'DETALLE', fmt_title)

        # =========================
        # ENCABEZADOS
        # =========================
        headers = ['CODIGO', 'DESCRIPCION', 'MARCA', 'RUBRO', 'UNIDADES', 'UxB', 'BULTOS', 'PRECIO DE LISTA', 'VALOR']
        for col, h in enumerate(headers):
            worksheet.write(8, col, h, fmt_header)

        # =========================
        # DOMAIN
        # =========================
        domain = [('sale_ok', '=', True)]
        products = self.env['product.template'].search(domain)
        if not products:
            raise ValidationError("No se encontraron productos.")

        # =========================
        # DATA
        # =========================
        row = 9  # empezamos justo debajo de headers
        total_valorizado = 0.0
        total_bultos = 0.0
        total_precio_lista = 0.0
        total_contenedores = 0.0
        contenedores_x_entrar = 0.0
        for product in products:
            #marketing exclusion
            parent_id = self.env['product.category'].search([('name', 'in', ['MARKETING', 'INSUMOS'])], limit=1)
            if parent_id and product.categ_id.parent_id and product.categ_id.parent_id.id == parent_id.id:
                continue
            stock_erp = self.env['stock.erp'].search([('product_id', '=', product.id)], limit=1)
            if not stock_erp or stock_erp.fisico_unidades <= 0:
                continue
            
            pricelist_item = self.env['product.pricelist.item'].search([('pricelist_id', '=', self.price_list_id.id), ('product_tmpl_id', '=', product.id)], limit=1)
            valor = pricelist_item.fixed_price * stock_erp.fisico_unidades if pricelist_item else 0.0
            bultos = (stock_erp.fisico_unidades / stock_erp.uxb) if stock_erp.uxb else 0.0

            worksheet.write(row, 0, product.default_code, fmt_text2)
            worksheet.write(row, 1, product.name, fmt_text)
            worksheet.write(row, 2, product.product_brand_id.name if product.product_brand_id else '', fmt_text2)
            worksheet.write(row, 3, product.categ_id.parent_id.name if product.categ_id.parent_id else '', fmt_text2)
            worksheet.write(row, 4, stock_erp.fisico_unidades, fmt_int)
            worksheet.write(row, 5, stock_erp.uxb, fmt_int)
            worksheet.write(row, 6, bultos, fmt_dec2)
            worksheet.write(row, 7, pricelist_item.fixed_price if pricelist_item else 0.0, fmt_dec2)
            worksheet.write(row, 8, valor, fmt_dec2)
            row += 1
            total_valorizado += valor
            total_bultos += bultos
            total_precio_lista += pricelist_item.fixed_price if pricelist_item else 0.0
        # =========================
        #totales
        worksheet.write(row, 3, 'TOTALS:', fmt_header)
        worksheet.write(row, 6, total_bultos, fcont_dec)
        worksheet.write(row, 7, total_precio_lista, fcont_dec)
        worksheet.write(row, 8, total_valorizado, fcont_dec)
        # =========================
        #DEBAJO DE RESUMEN, ANTES DE DETALLE
        worksheet.write(3, 0, 'TOTAL VALORIZADO:', rm_text)
        worksheet.write(3, 1, total_valorizado, fcont_dec2)
        worksheet.write(4, 0, 'TOTAL BULTOS:', rm_text)
        worksheet.write(4, 1, total_bultos, fcont_dec2)
        worksheet.write(5, 0, 'TOTAL CONTENEDORES:', rm_text)
        worksheet.write(5, 1, total_contenedores, fcont_dec2)
        worksheet.write(6, 0, 'CONTENEDORES POR ENTRAR:', rm_text)
        worksheet.write(6, 1, contenedores_x_entrar, fcont_dec2)
        
        workbook.close()
        output.seek(0)
        archivo_excel = base64.b64encode(output.read())
        fecha_str = date.today().strftime('%d-%m-%Y')
        attachment = self.env['ir.attachment'].create({
            'name': f'Reporte - Valorizado - {fecha_str}.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': f'Reporte - Valorizado - {fecha_str}.xlsx',
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