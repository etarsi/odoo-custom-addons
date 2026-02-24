from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import xlsxwriter
from . import excel
import os
import tempfile

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

class ReporteFacturaWizard(models.TransientModel):
    _name = 'reporte.factura.wizard'
    _description = 'Wizard para Exportar Facturas'

    date_start = fields.Date('Fecha inicio', required=True, default=fields.Date.context_today)
    date_end = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    partner_ids = fields.Many2many(
        'res.partner',
        string='Clientes/Proveedores',
    )
    
    is_out_invoice = fields.Boolean(string='Factura de Cliente', default=True)
    is_out_refund = fields.Boolean(string='Nota de Crédito de Cliente')
    is_in_invoice = fields.Boolean(string='Factura de Proveedor')
    is_in_refund = fields.Boolean(string='Nota de Crédito de Proveedor')
    
    is_draft = fields.Boolean(string='Borrador')
    is_posted = fields.Boolean(string='Publicado', default=True)
    is_cancel = fields.Boolean(string='Cancelados')
    marca_ids = fields.Many2many(
        'product.brand',
        string='Marca',
        help='Filtrar por Marca de Producto'
    )
    user_ids = fields.Many2many(
        'res.users',
        string='Comercial',
        help='Filtrar por Comercial'
    )
    
    def action_generar_excel(self):
        self.ensure_one()

        # Validaciones
        if not self.date_start or not self.date_end:
            raise ValidationError("La Fecha de Inicio y Final es Requerido")
        if self.date_end < self.date_start:
            raise ValidationError("La Fecha Final del reporte de facturas, no puede ser menor a la Fecha de Inicio")

        # Tipos seleccionados
        selected_types = []
        if self.is_out_invoice: selected_types.append('out_invoice')
        if self.is_out_refund:  selected_types.append('out_refund')
        if self.is_in_invoice:  selected_types.append('in_invoice')
        if self.is_in_refund:   selected_types.append('in_refund')

        # Estados seleccionados
        selected_states = []
        if self.is_draft:  selected_states.append('draft')
        if self.is_posted: selected_states.append('posted')
        if self.is_cancel: selected_states.append('cancel')

        # Dominio sobre account.move.line (más eficiente que traer moves y después lines)
        line_domain = [
            ('move_id.invoice_date', '>=', self.date_start),
            ('move_id.invoice_date', '<=', self.date_end),
            ('display_type', '=', False),   # fuera secciones/notas
            ('product_id', '!=', False),    # fuera líneas sin producto
        ]
        if selected_states:
            line_domain.append(('move_id.state', 'in', selected_states))
        if selected_types:
            line_domain.append(('move_id.move_type', 'in', selected_types))
        if self.partner_ids:
            line_domain.append(('move_id.partner_id', 'in', self.partner_ids.ids))
        if self.user_ids:
            line_domain.append(('move_id.invoice_user_id', 'in', self.user_ids.ids))
        if self.marca_ids:
            line_domain.append(('product_id.product_brand_id', 'in', self.marca_ids.ids))

        # Archivo temporal (reduce RAM vs BytesIO + in_memory)
        tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        tmp_path = tmp.name
        tmp.close()

        workbook = xlsxwriter.Workbook(tmp_path, {'constant_memory': True})
        worksheet = workbook.add_worksheet('Facturas')

        # Columnas
        worksheet.set_column(0, 0, 20)
        worksheet.set_column(1, 2, 15)
        worksheet.set_column(3, 3, 10)
        worksheet.set_column(4, 4, 25)
        worksheet.set_column(5, 6, 15)
        worksheet.set_column(7, 7, 10)
        worksheet.set_column(8, 8, 45)
        worksheet.set_column(9, 10, 15)
        worksheet.set_column(11, 12, 10)
        worksheet.set_column(13, 13, 15)
        worksheet.set_column(14, 14, 20)
        worksheet.set_column(15, 15, 15)
        worksheet.set_column(16, 16, 40)
        worksheet.set_column(17, 18, 25)
        worksheet.set_column(19, 22, 20)

        # Formatos
        formato_encabezado = excel.formato_encabezado(workbook)
        formato_celdas_izquierda = excel.formato_celda_izquierda(workbook)
        formato_celdas_derecha = excel.formato_celda_derecha(workbook)
        formato_celdas_decimal = excel.formato_celda_decimal(workbook)

        # Encabezados
        headers = [
            'DOCUMENTO','FECHA','MES','AÑO','CLIENTE','ETIQUETA CLIENTE','COMERCIAL',
            'CÓDIGO','DESCRIPCIÓN','PRECIO UNITARIO','UNIDADES','UxB','BULTOS','DESCUENTO',
            'SUBTOTAL','EMPRESA','RUBRO','CATEGORIA','MARCA',
            'CONTRATO DISNEY','SUBCONTRATO DISNEY','PERSONAJE DISNEY','PROPIEDAD DISNEY'
        ]
        for col, h in enumerate(headers):
            worksheet.write(0, col, h, formato_encabezado)

        MoveLine = self.env['account.move.line']

        row = 1
        batch = 2000
        offset = 0

        while True:
            lines = MoveLine.search(line_domain, order='id', limit=batch, offset=offset)
            if not lines:
                break

            # (Opcional) prefetch “barato” dentro del batch
            _ = lines.mapped('move_id')
            _ = lines.mapped('product_id')

            for line in lines:
                move = line.move_id
                product = line.product_id
                partner = move.partner_id

                # Fechas
                if move.invoice_date:
                    date_facture = move.invoice_date.strftime('%d/%m/%Y')
                    month_num = move.invoice_date.strftime('%m')
                    month = MESES_ES.get(month_num, '')
                    year = move.invoice_date.strftime('%Y')
                else:
                    date_facture = month = year = ''

                categorias = '-'.join(partner.category_id.mapped('name')) if partner.category_id else ''

                # UxB / bultos
                uxb_id = product.packaging_ids[:1]
                uxb_id = uxb_id[0] if uxb_id else False

                bultos = 0.0
                if uxb_id and uxb_id.qty:
                    bultos = line.quantity / uxb_id.qty

                quantity = line.quantity
                subtotal = line.price_subtotal
                if move.move_type in ('out_refund', 'in_refund'):
                    quantity = -abs(line.quantity)
                    subtotal = -abs(line.price_subtotal) if line.price_subtotal > 0 else line.price_subtotal
                    
                    
                #VALIDAR SI EL PRODUCTO TIENE PROPIEDAD 
                if product:
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
                else:
                    property_id = False
                    x_contract_id = False
                    x_subcontract_id = False
                    x_character_id = False

                worksheet.write(row, 0, move.name or '', formato_celdas_izquierda)
                worksheet.write(row, 1, date_facture, formato_celdas_derecha)
                worksheet.write(row, 2, month, formato_celdas_derecha)
                worksheet.write(row, 3, year, formato_celdas_derecha)
                worksheet.write(row, 4, partner.name or '', formato_celdas_izquierda)
                worksheet.write(row, 5, categorias or '', formato_celdas_izquierda)
                worksheet.write(row, 6, (move.invoice_user_id.name or '') if move.invoice_user_id else '', formato_celdas_izquierda)

                worksheet.write(row, 7, product.default_code or '', formato_celdas_izquierda)
                worksheet.write(row, 8, product.display_name or product.name or '', formato_celdas_izquierda)

                worksheet.write(row, 9, line.price_unit or 0.0, formato_celdas_decimal)
                worksheet.write(row, 10, quantity or 0.0, formato_celdas_decimal)
                worksheet.write(row, 11, uxb_id.name if uxb_id else '', formato_celdas_izquierda)
                worksheet.write(row, 12, bultos or 0.0, formato_celdas_decimal)
                worksheet.write(row, 13, line.discount or 0.0, formato_celdas_decimal)
                worksheet.write(row, 14, subtotal or 0.0, formato_celdas_decimal)
                worksheet.write(row, 15, move.company_id.name or '', formato_celdas_izquierda)

                worksheet.write(row, 16, (product.categ_id.parent_id.name or '') if product.categ_id and product.categ_id.parent_id else '', formato_celdas_izquierda)
                worksheet.write(row, 17, (product.categ_id.name or '') if product.categ_id else '', formato_celdas_izquierda)
                worksheet.write(row, 18, (product.product_brand_id.name or '') if product.product_brand_id else '', formato_celdas_izquierda)

                worksheet.write(row, 19, x_contract_id.x_name if x_contract_id else '', formato_celdas_izquierda)
                worksheet.write(row, 20, x_subcontract_id.x_name if x_subcontract_id else '', formato_celdas_izquierda)
                worksheet.write(row, 21, x_character_id.x_name if x_character_id else '', formato_celdas_izquierda)
                worksheet.write(row, 22, property_id.x_name if property_id else '', formato_celdas_izquierda)

                row += 1

            offset += batch

        workbook.close()

        # Adjuntar (lee el archivo final)
        with open(tmp_path, 'rb') as f:
            archivo_excel = base64.b64encode(f.read())

        # limpiar temp
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        attachment = self.env['ir.attachment'].create({
            'name': 'reporte_factura.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': 'reporte_factura.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }