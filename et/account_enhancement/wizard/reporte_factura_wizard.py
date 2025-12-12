from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter
from . import excel

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
        # Crear un buffer en memoria
        output = io.BytesIO()
        # Crear el archivo Excel
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Facturas')
        # Agrupados por rangos consecutivos con mismo ancho
        worksheet.set_column(0, 0, 20)   # DOCUMENTO
        worksheet.set_column(1, 2, 15)   # FECHA y MES (ambas 15)
        worksheet.set_column(3, 3, 10)   # AÑO
        worksheet.set_column(4, 4, 25)   # CLIENTE
        worksheet.set_column(5, 6, 15)   # ETIQUETA CLIENTE y COMERCIAL (ambas 15)
        worksheet.set_column(7, 7, 10)   # CÓDIGO
        worksheet.set_column(8, 8, 45)   # DESCRIPCIÓN (ancha para textos largos)
        worksheet.set_column(9, 10, 15)  # PRECIO UNITARIO y UNIDADES (ambas 15)
        worksheet.set_column(11, 12, 10) # UxB y BULTOS (ambas 10)
        worksheet.set_column(13, 13, 15) # DESCUENTO
        worksheet.set_column(14, 14, 20) # SUBTOTAL
        worksheet.set_column(15, 15, 15) # EMPRESA
        worksheet.set_column(16, 16, 40) # RUBRO
        worksheet.set_column(17, 18, 25) # CATEGORIA y MARCA (ambas 25)
        worksheet.set_column(19, 22, 20) # CONTRATO DISNEY hasta PROPIEDAD DISNEY (todas 20)
        
        #formato de celdas
        formato_encabezado = excel.formato_encabezado(workbook)
        formato_celdas_izquierda = excel.formato_celda_izquierda(workbook)
        formato_celdas_derecha = excel.formato_celda_derecha(workbook)
        formato_celdas_decimal = excel.formato_celda_decimal(workbook)
        # Escribir encabezados
        worksheet.write(0, 0, 'DOCUMENTO', formato_encabezado)
        worksheet.write(0, 1, 'FECHA', formato_encabezado)
        worksheet.write(0, 2, 'MES', formato_encabezado)
        worksheet.write(0, 3, 'AÑO', formato_encabezado)
        worksheet.write(0, 4, 'CLIENTE', formato_encabezado)
        worksheet.write(0, 5, 'ETIQUETA CLIENTE', formato_encabezado)
        worksheet.write(0, 6, 'COMERCIAL', formato_encabezado)
        worksheet.write(0, 7, 'CÓDIGO', formato_encabezado)
        worksheet.write(0, 8, 'DESCRIPCIÓN', formato_encabezado)
        worksheet.write(0, 9, 'PRECIO UNITARIO', formato_encabezado)
        worksheet.write(0, 10, 'UNIDADES', formato_encabezado)
        worksheet.write(0, 11, 'UxB', formato_encabezado)
        worksheet.write(0, 12, 'BULTOS', formato_encabezado)
        worksheet.write(0, 13, 'DESCUENTO', formato_encabezado)
        worksheet.write(0, 14, 'SUBTOTAL', formato_encabezado)
        worksheet.write(0, 15, 'EMPRESA', formato_encabezado)
        worksheet.write(0, 16, 'RUBRO', formato_encabezado)
        worksheet.write(0, 17, 'CATEGORIA', formato_encabezado)
        worksheet.write(0, 18, 'MARCA', formato_encabezado)
        worksheet.write(0, 19, 'CONTRATO DISNEY', formato_encabezado)
        worksheet.write(0, 20, 'SUBCONTRATO DISNEY', formato_encabezado)
        worksheet.write(0, 21, 'PERSONAJE DISNEY', formato_encabezado)
        worksheet.write(0, 22, 'PROPIEDAD DISNEY', formato_encabezado)

        # Buscar facturas en el rango de fechas
        domain = [
            ('invoice_date', '>=', self.date_start),
            ('invoice_date', '<=', self.date_end),
        ]
        if not self.date_start or not self.date_end:
            raise ValidationError("La Fecha de Inicio y Final es Requerido")
        if self.date_end < self.date_start:
            raise ValidationError("La Fecha Final del reporte de facturas, no puede ser menor a la Fecha de Inicio")
        
        # Recolectar los tipos seleccionados en una lista
        selected_types = []
        if self.is_out_invoice:
            selected_types.append('out_invoice')
        if self.is_out_refund:
            selected_types.append('out_refund')
        if self.is_in_invoice:
            selected_types.append('in_invoice')
        if self.is_in_refund:
            selected_types.append('in_refund')
            
        # Recolectar los estados seleccionados en una lista
        selected_states = []
        if self.is_draft:
            selected_states.append('draft')
        if self.is_posted:
            selected_states.append('posted')
        if self.is_cancel:
            selected_states.append('cancel') 
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        if selected_states:
            domain.append(('state', 'in', selected_states))
        if selected_types:
            domain.append(('move_type', 'in', selected_types))
        if self.user_ids:
            domain.append(('invoice_user_id', 'in', self.user_ids.ids))
        if self.marca_ids:
            domain.append(('invoice_line_ids.product_id.product_brand_id', 'in', self.marca_ids.ids))
        facturas = self.env['account.move'].search(domain)
        # Escribir datos
        row = 1
        for factura in facturas:
            facturas_lines = factura.invoice_line_ids
            # Fechas formateadas
            date_facture = factura.invoice_date.strftime('%d/%m/%Y') if factura.invoice_date else ''
            month_num = factura.invoice_date.strftime('%m') if factura.invoice_date else ''
            month = MESES_ES.get(month_num, '') if month_num else ''
            year = factura.invoice_date.strftime('%Y') if factura.invoice_date else ''
            categorias = '-'.join(factura.partner_id.category_id.mapped('name')) if factura.partner_id.category_id else ''
            if facturas_lines:
                for line in facturas_lines:
                    if not line.product_id and (line.quantity==0 or line.price_unit==0 or line.price_subtotal==0):
                        continue
                    # solo imprimir las lineas que tengan esa marca
                    if self.marca_ids:
                        if not line.product_id.product_brand_id:
                            continue
                        else:
                            if line.product_id.product_brand_id.id not in self.marca_ids.ids:
                                continue
                    uxb_id = line.product_id.packaging_ids[0] if line.product_id.packaging_ids else False
                    bultos = 0
                    if uxb_id:
                        bultos = line.quantity/uxb_id.qty
                    quantity = line.quantity
                    subtotal = line.price_subtotal
                    if factura.move_type in ('out_refund', 'in_refund'):
                        quantity = -abs(line.quantity)
                        if line.price_subtotal > 0:
                            subtotal = -abs(line.price_subtotal)
                        else:
                            subtotal = line.price_subtotal
                    worksheet.write(row, 0, factura.name, formato_celdas_izquierda)
                    worksheet.write(row, 1, date_facture, formato_celdas_derecha)
                    worksheet.write(row, 2, month, formato_celdas_derecha)
                    worksheet.write(row, 3, year, formato_celdas_derecha)
                    worksheet.write(row, 4, factura.partner_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 5, categorias, formato_celdas_izquierda)
                    worksheet.write(row, 6, factura.invoice_user_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 7, line.product_id.default_code if line.product_id.default_code else '', formato_celdas_izquierda)
                    worksheet.write(row, 8, line.product_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 9, line.price_unit, formato_celdas_decimal)
                    worksheet.write(row, 10, quantity, formato_celdas_decimal)
                    worksheet.write(row, 11, uxb_id.name if uxb_id else '', formato_celdas_izquierda)
                    worksheet.write(row, 12, bultos, formato_celdas_decimal)
                    worksheet.write(row, 13, line.discount, formato_celdas_decimal)
                    worksheet.write(row, 14, subtotal, formato_celdas_decimal)
                    worksheet.write(row, 15, factura.company_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 16, line.product_id.categ_id.parent_id.name if line.product_id.categ_id.parent_id else '', formato_celdas_izquierda)
                    worksheet.write(row, 17, line.product_id.categ_id.name if line.product_id.categ_id else '', formato_celdas_izquierda)
                    worksheet.write(row, 18, line.product_id.product_brand_id.name if line.product_id.product_brand_id else '', formato_celdas_izquierda)
                    worksheet.write(row, 19, line.product_id.x_contract_id.x_name if line.product_id.x_contract_id else ' ', formato_celdas_izquierda)
                    worksheet.write(row, 20, line.product_id.x_subcontract_id.x_name if line.product_id.x_subcontract_id else ' ', formato_celdas_izquierda)
                    worksheet.write(row, 21, line.product_id.x_character_id.x_name if line.product_id.x_character_id else ' ', formato_celdas_izquierda)
                    worksheet.write(row, 22, line.product_id.x_property_id.x_name if line.product_id.x_property_id else ' ', formato_celdas_izquierda)
                    row += 1

        workbook.close()
        output.seek(0)
        # Codificar el archivo en base64
        archivo_excel = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'reporte_factura.xlsx',  # Nombre del archivo con fecha
            'type': 'binary',  # Tipo binario para archivos
            'datas': archivo_excel,  # Datos codificados en base64
            'store_fname': f'reporte_factura.xlsx',  # Nombre para almacenamiento
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # Tipo MIME correcto
        })
        # Retornar acción para descargar el archivo
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',  # URL para descarga
            'target': 'self'  # Abrir en la misma ventana
        }