from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter, logging
from . import excel
_logger = logging.getLogger(__name__)


class ReportAccountReturnWizard(models.TransientModel):
    _name = 'report.account.return.wizard'
    _description = 'Reporte de devoluciones en Facturas'

    temporada = fields.Selection(string='Temporada', selection=[
        ('t_all', 'Todas las Temporadas'),
        ('t_nino_2025', 'Temporada Niño 2025'),
        ('t_nav_2025', 'Temporada Navidad 2025'),
    ], required=True, default='t_nav_2025', help='Seleccionar la temporada para el reporte')  
    partner_ids = fields.Many2many('res.partner', string='Clientes', help='Seleccionar un Cliente para filtrar')
    category_ids = fields.Many2many('product.category', string='Categorías de Producto', help='Filtrar por categorías de producto', domain=[('parent_id', '=', False)])
    company_ids = fields.Many2many('res.company', string='Compañías', help='Filtrar por Compañías')
    product_ids = fields.Many2many('product.product', string='Productos', help='Filtrar por Productos', required=True)

    def action_generar_excel(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('REPORTE DEVOLUCIONES FACTURAS')
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
        worksheet.merge_range(0, 0, 0, 11, ('REPORTE DE DEVOLUCIONES EN FACTURAS'), fmt_title)
        # =========================
        # COLUMNAS DE LA HOJA REPORTE DE ENTREGA
        # =========================
        worksheet.set_column(0, 0, 15)      # Fecha
        worksheet.set_column(1, 1, 30)    # Factura
        worksheet.set_column(2, 2, 30)      # codigo
        worksheet.set_column(3, 3, 60)      # descripcion
        worksheet.set_column(4, 4, 20)      # cantidad
        worksheet.set_column(5, 5, 20)      # precio unitario
        worksheet.set_column(6, 6, 30)      # descuento
        worksheet.set_column(7, 7, 20)      # impuesto
        worksheet.set_column(8, 8, 55)      # subtotal
        worksheet.set_column(9, 9, 20)      # compañía
        # Alto de filas de título/encabezado
        worksheet.set_row(0, 20)
        worksheet.set_row(1, 18)
        # =========================
        # ENCABEZADOS
        # =========================
        headers = ['FECHA', 'FACTURA', 'CODIGO', 'DESCRIPCIÓN', 'CANTIDAD', 'PRECIO UNITARIO', 'DESCUENTO', 'IMPUESTO', 'SUBTOTAL', 'COMPAÑIA']
        for col, h in enumerate(headers):
            worksheet.write(1, col, h, fmt_header)
            
            
        # =========================
        # DOMAIN
        # =========================
        domain = [('move_id.state', '=', 'done'), ('move_id.move_type', 'in', ['out_invoice', 'out_refund'])]
        if self.temporada != 't_all':
            if self.temporada == 't_nino_2025':
                domain += [('create_date', '>=', date(2025, 3, 1)), ('create_date', '<=', date(2025, 8, 31))]
            elif self.temporada == 't_nav_2025':
                domain += [('create_date', '>=', date(2025, 9, 1)), ('create_date', '<=', date(2026, 2, 28))]
        if self.partner_ids:
            domain += [('move_id.partner_id', 'in', self.partner_ids.ids)]
        if self.product_ids:
            domain += [('product_id', 'in', self.product_ids.ids)]            
        account_move_lines = self.env['account.move.line'].search(domain)
        if not account_move_lines:
            raise ValidationError("No se encontraron albaranes para los criterios seleccionados.")

        # =========================
        # DATA
        # =========================
        row = 2  # empezamos justo debajo de headers
        for line in account_move_lines:
            date_done = line.move_id.invoice_date.strftime('%d/%m/%Y') if line.move_id.invoice_date else ''
            #DATOS DE LAS FILAS DE REPORTE ENTREGA
            worksheet.write(row, 0, date_done, fmt_text2)
            worksheet.write(row, 1, line.move_id.name, fmt_text)
            worksheet.write(row, 2, line.product_id.default_code or '', fmt_text)
            worksheet.write(row, 3, line.product_id.name or '', fmt_text2)
            worksheet.write(row, 4, line.quantity, fmt_moneda)
            worksheet.write(row, 5, line.price_unit, fmt_moneda)
            worksheet.write(row, 6, line.discount, fmt_text2)
            worksheet.write(row, 7, line.tax_ids.name if line.tax_ids else '', fmt_text2)
            worksheet.write(row, 8, line.price_subtotal, fmt_text)
            worksheet.write(row, 9, line.company_id.name, fmt_text)
            row += 1
        workbook.close()
        output.seek(0)

        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'Reporte Facturas-devolucion - {fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': f'Reporte Facturas-devolucion - {fields.Date.today()}.xlsx',
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