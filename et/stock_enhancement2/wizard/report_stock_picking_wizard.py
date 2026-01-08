from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter, logging
from . import excel
_logger = logging.getLogger(__name__)


class ReportStockPickingWizard(models.TransientModel):
    _name = 'report.stock.picking.wizard'
    _description = 'Wizard para Exportar Facturas'

    temporada = fields.Selection(string='Temporada', selection=[
        ('t_nino_2025', 'Temporada Niño 2025'),
        ('t_nav_2025', 'Temporada Navidad 2025'),
    ], required=True, default='t_nav_2025', help='Seleccionar la temporada para el reporte')  
    partner_id = fields.Many2one('res.partner', string='Cliente', help='Seleccionar un Cliente para filtrar', domain=[('is_company', '=', True)])
    parent_ids = fields.Many2many('res.partner', string='Cliente Relacionado', help='Filtrar por empresa padre y los que pertenecen a ella',
                                domain=[('company_type', '=', 'person'), ('parent_id', '!=', False)])
    category_ids = fields.Many2many('product.category', string='Categorías de Producto', help='Filtrar por categorías de producto', domain=[('parent_id', '=', False)])
    

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
        worksheet = workbook.add_worksheet('Inventario')

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
        fmt_dec2 = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0.00'})

        # =========================
        # COLUMNAS
        # =========================
        worksheet.set_column(0, 0, 15)  # FECHA
        worksheet.set_column(1, 1, 60)  # CLIENTE
        worksheet.set_column(2, 2, 15)  # PEDIDO VENTA
        worksheet.set_column(3, 3, 15)  # CODIGO
        worksheet.set_column(4, 4, 60)  # DESCRIPCION
        worksheet.set_column(5, 5, 12)  # UNIDADES
        worksheet.set_column(6, 6, 10)  # UxB
        worksheet.set_column(7, 7, 12)  # BULTOS
        worksheet.set_column(8, 8, 28)  # RUBRO
        worksheet.set_column(9, 9, 20)  # ESTADO
        worksheet.set_column(10, 10, 60)  # Nro TRANSFERENCIA
        worksheet.set_column(11, 11, 20)  # COMPAÑIA
        

        # Alto de filas de título/encabezado
        worksheet.set_row(0, 20)
        worksheet.set_row(1, 18)

        # =========================
        # TITULO
        # =========================
        worksheet.merge_range(0, 0, 0, 11, (self.partner_id.name or 'TODOS LOS CLIENTES').upper(), fmt_title)

        # =========================
        # ENCABEZADOS
        # =========================
        headers = ['FECHA', 'CLIENTE', 'Nro PEDIDO', 'CODIGO', 'DESCRIPCION', 'UNIDADES', 'UxB', 'BULTOS', 'RUBRO', 'ESTADO', 'Nro TRANSFERENCIA', 'COMPAÑIA']
        for col, h in enumerate(headers):
            worksheet.write(1, col, h, fmt_header)

        # =========================
        # DOMAIN
        # =========================
        domain = [('state', '!=', 'cancel'), ('picking_type_id.code', '=', 'outgoing')]
        clientes_ids = []

        if self.temporada == 't_nino_2025':
            domain += [('create_date', '>=', date(2025, 3, 1)), ('create_date', '<=', date(2025, 8, 31))]
        elif self.temporada == 't_nav_2025':
            domain += [('create_date', '>=', date(2025, 9, 1)), ('create_date', '<=', date(2026, 2, 28))]

        if self.partner_id:
            clientes_ids.append(self.partner_id.id)
        if self.parent_ids:
            clientes_ids += self.parent_ids.ids
        if clientes_ids:
            domain += [('partner_id', 'in', clientes_ids)]
            
        stocks_pickings = self.env['stock.picking'].search(domain)
        if not stocks_pickings:
            raise ValidationError("No se encontraron albaranes para los criterios seleccionados.")

        # =========================
        # DATA
        # =========================
        row = 2  # empezamos justo debajo de headers
        for stock_picking in stocks_pickings:
            domain_moves = [('picking_id', '=', stock_picking.id)]
            if self.category_ids:
                domain_moves += [('product_id.categ_id.parent_id', 'in', self.category_ids.ids)]
            else:
                domain_moves += [('product_id.categ_id.parent_id', '!=', False)]
            pickings_moves = self.env['stock.move'].search(domain_moves)
                
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
            
            # Fecha de creación del albarán
            picking_date = stock_picking.create_date.strftime('%d/%m/%Y') if stock_picking.create_date else ''
            #Sacar el nombre del cliente si tiene 
            partner = stock_picking.partner_id
            if partner:
                parent_name = partner.parent_id.name or ""
                child_name = partner.name or ""
                if partner.company_type == "person" and parent_name:
                    partner_name = f"{parent_name} / {child_name}"
                else:
                    partner_name = child_name
            else:
                partner_name = ""
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

                worksheet.write(row, 0, picking_date, fmt_text2)
                worksheet.write(row, 1, partner_name, fmt_text)
                worksheet.write(row, 2, stock_picking.sale_id.name if stock_picking.sale_id else '', fmt_text2)
                worksheet.write(row, 3, move.product_id.default_code or '', fmt_text2)
                worksheet.write(row, 4, move.product_id.name or '', fmt_text)
                worksheet.write_number(row, 5, unidades, fmt_int)
                worksheet.write_number(row, 6, uxb, fmt_int)
                worksheet.write_number(row, 7, bultos, fmt_dec2)
                worksheet.write(row, 8, move.product_id.categ_id.parent_id.name or '', fmt_text)
                worksheet.write(row, 9, estado_txt, fmt_text)
                worksheet.write(row, 10, stock_picking.name, fmt_text)
                worksheet.write(row, 11, stock_picking.company_id.name, fmt_text2)
                row += 1
        workbook.close()
        output.seek(0)

        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'Pendientes {self.partner_id.name.lower() if self.partner_id else "todos"} - {fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': f'Pendientes {self.partner_id.name.lower() if self.partner_id else "todos"} - {fields.Date.today()}.xlsx',
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