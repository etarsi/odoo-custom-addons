from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import re
from decimal import Decimal, InvalidOperation
from odoo.tools.float_utils import float_round
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
    price_list_id = fields.Many2one('product.pricelist', string='Lista de Precios', help='Seleccionar una Lista de Precios para valorizar el stock', compute='_compute_default_price_list', required=True)
    

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        default_pricelist = self.env['product.pricelist'].search([('is_default', '=', True)], limit=1)
        res['price_list_id'] = default_pricelist.id if default_pricelist else False
        return res    

    def _compute_default_price_list(self):
        default_pricelist = self.env['product.pricelist'].search([('is_default', '=', True)], limit=1)
        if not default_pricelist:
            raise ValidationError("No se encontró una lista de precios por defecto. Por favor, configure una lista de precios como predeterminada.")
        self.price_list_id = default_pricelist


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
        fmt_total = workbook.add_format({
            'bold': True,
            'font_color': '#FFFFFF',
            'bg_color': '#000000',
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#FFFFFF',
        })
        fmt_text_l = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter'})
        fmt_text_c = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        fmt_int = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0'})
        fmt_tr_int_no_border = workbook.add_format({'bold': True, 'align': 'right', 'valign': 'vcenter', 'num_format': '0'})
        fmt_total_bultos = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0.00', 'bold': True})
        fmt_dec = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0.00'})
        fmt_dec_no_border_c = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'num_format': '0.00'})
        fmt_dec_no_border_l = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'num_format': '0.00'})
        fmt_text_bold_l = workbook.add_format({'align': 'right', 'valign': 'vcenter', 'bold': True})
        #formato contabilidad
        fmt_contab = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '_($* #,##0_);_($* (#,##0);_($* "-"??_);_(@_)'})
        fmt_total_contab = workbook.add_format({'border': 1, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'num_format': '_($* #,##0_);_($* (#,##0);_($* "-"??_);_(@_)'})
        fmt_tr_contab_no_border = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'num_format': '_($* #,##0_);_($* (#,##0);_($* "-"??_);_(@_)'})

        # =========================
        # COLUMNAS
        # =========================
        worksheet.set_column(0, 0, 25)  # CODIGO
        worksheet.set_column(1, 1, 60)  # DESCRIPCION
        worksheet.set_column(2, 2, 25)  # MARCA
        worksheet.set_column(3, 3, 25)  # RUBRO
        worksheet.set_column(4, 4, 12)  # UNIDADES
        worksheet.set_column(5, 5, 12)  # UxB
        worksheet.set_column(6, 6, 12)  # BULTOS
        worksheet.set_column(7, 7, 18)  # PRECIO DE LISTA
        worksheet.set_column(8, 8, 18)  # VALOR
        

        # Alto de filas de título/encabezado
        worksheet.set_row(0, 20)
        worksheet.set_row(1, 18)
        # =========================
        # TITULO
        # =========================
        worksheet.merge_range(0, 0, 0, 8, 'REPORTE DE STOCK VALORIZADO', fmt_title)
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
        products = self.env['product.product'].search([])
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

        excluded_product_categorys = set(
            self.env['product.category'].search([('name', 'in', ['MARKETING', 'INSUMOS', 'REPUESTOS DE BATERIA'])]).ids
        )
        stock_erps = self.env['stock.erp'].search([
            ('fisico_unidades', '>', 0),
            ('product_id', '!=', False),
        ])
        products = stock_erps.mapped('product_id')
        
        
        # Prearmar mapa de precios por template (lookup O(1))
        #PRECIO SETEADO TEMPORAL
        price_list_id = self.env['product.pricelist'].browse(45)
        items = price_list_id.item_ids.filtered(lambda i: i.product_tmpl_id)
        items = items.sorted(key=lambda i: i.id)
        fixed_price_by_tmpl = {}
        for it in items:
            fixed_price_by_tmpl.setdefault(it.product_tmpl_id.id, it.fixed_price)

        for stock_erp in stock_erps:
            product = stock_erp.product_id
            if not product:
                continue

            parent_categ = product.categ_id.parent_id
            product_categ = product.categ_id
            if parent_categ and parent_categ.id in excluded_product_categorys:
                continue
            if product_categ and product_categ.id in excluded_product_categorys:
                continue

            # Precio lista con IVA
            fixed_price = fixed_price_by_tmpl.get(product.product_tmpl_id.id, 0.0)
            valor_fixed_price = fixed_price * 1.21 if fixed_price else 0.0
            valor_fixed_price = valor_fixed_price * 1.10
            valor_fixed_price = round(valor_fixed_price, 0)
            valor = valor_fixed_price * stock_erp.fisico_unidades if fixed_price else 0.0
            # redondeo a entero, HALF-UP
            valor = float_round(valor, precision_rounding=1.0, rounding_method='HALF-UP')
            valor = int(valor)
            #calculo bultos
            bultos = (stock_erp.fisico_unidades / stock_erp.uxb) if stock_erp.uxb else 0.0
            
            #LISTABA DE PRECIOS
            worksheet.write(row, 0, product.default_code, fmt_text_c)
            worksheet.write(row, 1, product.name, fmt_text_l)
            worksheet.write(row, 2, product.product_brand_id.name if product.product_brand_id else '', fmt_text_c)
            worksheet.write(row, 3, product.categ_id.parent_id.name if product.categ_id.parent_id else '', fmt_text_c)
            worksheet.write(row, 4, stock_erp.fisico_unidades, fmt_int)
            worksheet.write(row, 5, stock_erp.uxb, fmt_int)
            worksheet.write(row, 6, bultos, fmt_dec)
            worksheet.write(row, 7, valor_fixed_price, fmt_contab)
            worksheet.write(row, 8, valor, fmt_contab)
            row += 1
            total_valorizado += valor
            total_bultos += bultos
            total_precio_lista += valor_fixed_price
        # =========================
        #totales
        worksheet.merge_range(row, 0, row, 5, 'TOTALES:', fmt_total)
        worksheet.write(row, 6, total_bultos, fmt_total_bultos)
        worksheet.write(row, 7, total_precio_lista, fmt_total_contab)
        worksheet.write(row, 8, total_valorizado, fmt_total_contab)
        # =========================
        #DEBAJO DE RESUMEN, ANTES DE DETALLE
        total_bultos = float_round(total_bultos, 2)
        total_contenedores = float_round(total_bultos / 220.0, 2)  #asumiendo contenedor de 220 bultos
        worksheet.merge_range(2, 0, 2, 1, 'TOTAL VALORIZADO:', fmt_text_bold_l)
        worksheet.write(2, 2, total_valorizado, fmt_tr_contab_no_border)
        worksheet.merge_range(3, 0, 3, 1, 'TOTAL BULTOS:', fmt_text_bold_l)
        worksheet.write(3, 2, total_bultos, fmt_tr_int_no_border)
        worksheet.merge_range(4, 0, 4, 1, 'TOTAL CONTENEDORES:', fmt_text_bold_l)
        worksheet.write(4, 2, total_contenedores, fmt_tr_int_no_border)
        #worksheet.merge_range(5, 0, 5, 1, 'CONTENEDORES POR ENTRAR:', fmt_text_bold_l)
        #worksheet.write(5, 2, contenedores_x_entrar, fmt_tr_int_no_border)
        
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
        
    def calc_price_from_discount(self, base_price, discount_pct=0.0, surcharge=0.0, currency=None):
        base = self._to_decimal(base_price, field_name="base_price")
        disc = self._to_decimal(discount_pct, field_name="discount_pct")
        sur  = self._to_decimal(surcharge, field_name="surcharge")

        factor = Decimal("1") - (disc / Decimal("100"))
        price = (base * factor) + sur

        # Redondeo Odoo (si pasás moneda)
        if currency:
            return currency.round(float(price))
        return float(price)
    
    def _to_decimal(self, value, field_name="valor"):
        # None/False
        if value in (None, False, ''):
            return Decimal('0')

        # Si viene como (price, rule_id) o [price, ...]
        if isinstance(value, (list, tuple)) and value:
            return self._to_decimal(value[0], field_name=field_name)

        # Decimal directo
        if isinstance(value, Decimal):
            return value

        # int/float
        if isinstance(value, (int, float)):
            return Decimal(str(value))

        # string (con moneda / miles / coma decimal)
        if isinstance(value, str):
            s = value.strip()

            # deja sólo dígitos, coma, punto, signo menos
            s = re.sub(r"[^\d,.\-]", "", s)

            # si tiene ambos, decide separador decimal por el último que aparezca
            if "," in s and "." in s:
                if s.rfind(",") > s.rfind("."):
                    # 1.234,56 -> 1234.56
                    s = s.replace(".", "").replace(",", ".")
                else:
                    # 1,234.56 -> 1234.56
                    s = s.replace(",", "")
            elif "," in s:
                # 1234,56 -> 1234.56 (y si venía 1.234,56, ya sacamos letras, falta sacar miles)
                s = s.replace(".", "").replace(",", ".")
            else:
                # 1,234 -> 1234 (miles)
                s = s.replace(",", "")

            if s in ("", "-", ".", "-."):
                return Decimal("0")

            try:
                return Decimal(s)
            except InvalidOperation:
                raise UserError(_("No pude convertir %s a número: %r") % (field_name, value))

        # último intento
        try:
            return Decimal(str(value))
        except Exception:
            raise UserError(_("No pude convertir %s a número: %r (tipo %s)") % (field_name, value, type(value)))