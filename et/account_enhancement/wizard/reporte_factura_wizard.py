from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import date
import base64
import io
from . import excel

class ReporteFacturaWizard(models.TransientModel):
    _name = 'reporte.factura.wizard'
    _description = 'Wizard para Exportar Facturas'

    date_start = fields.Date('Fecha inicio', required=True, default=fields.Date.context_today)
    date_end = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    partner_ids = fields.Many2many(
        'res.partner',
        string='Clientes/Proveedores',
    )
    move_types = fields.Many2many(
        'ir.model.fields.selection',
        string='Tipos de comprobante',
        domain="[('field_id.model', '=', 'account.move'), ('field_id.name', '=', 'move_type')]",
        default=lambda self: self.env['ir.model.fields.selection'].search([
            ('field_id.model', '=', 'account.move'),
            ('field_id.name', '=', 'move_type'),
            ('value', '=', 'out_invoice')
        ]).ids
    )
    state_types = fields.Many2many(
        'ir.model.fields.selection',
        string='Estado de Factura',
        domain="[('field_id.model', '=', 'account.move'), ('field_id.name', '=', 'state')]",
        default=lambda self: self.env['ir.model.fields.selection'].search([
            ('field_id.model', '=', 'account.move'),
            ('field_id.name', '=', 'state'),
            ('value', '=', 'posted')
        ]).ids
    )
    
    def action_generar_excel(self):
        # Crear un buffer en memoria
        output = io.BytesIO()
        # Crear el archivo Excel
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Facturas')
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
        if self.fecha_fin < self.fecha_inicio:
            raise ValidationError("La Fecha Final del reporte de facturas, no puede ser menor a la Fecha de Inicio")
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        if self.state_types:
            domain.append(('state', 'in', [st.value for st in self.state_types]))
        if self.move_types:
            domain.append(('move_type', 'in', [mt.value for mt in self.move_types]))
        print(domain)
        facturas = self.env['account.move'].search(domain)
        # Escribir datos
        row = 1
        for factura in facturas:
            facturas_lines = self.env['account.move.line'].search([('move_id', '=', factura.id)])
            # Fechas formateadas
            date_facture = factura.invoice_date.strftime('%d/%m/%Y') if factura.invoice_date else ''
            month = factura.invoice_date.strftime('%m') if factura.invoice_date else ''
            year = factura.invoice_date.strftime('%Y') if factura.invoice_date else ''
            categorias = '-'.join(factura.partner_id.category_id.mapped('name')) if factura.partner_id.category_id else ''
            if facturas_lines:
                for line in facturas_lines:
                    if line.quantity==0 and line.price_unit==0:
                        pass;
                    uxb_id = line.product_id.seller_ids[0] if line.product_id.seller_ids else False
                    bultos = 0
                    if uxb_id:
                        bultos = line.quantity/uxb_id.qty
                    worksheet.write(row, 0, factura.name, formato_celdas_izquierda)
                    worksheet.write(row, 1, date_facture, formato_celdas_derecha)
                    worksheet.write(row, 2, month, formato_celdas_derecha)
                    worksheet.write(row, 3, year, formato_celdas_derecha)
                    worksheet.write(row, 4, factura.partner_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 5, categorias, formato_celdas_izquierda)
                    worksheet.write(row, 6, factura.invoice_user_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 7, line.product_id.default_code, formato_celdas_izquierda)
                    worksheet.write(row, 8, line.product_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 9, line.price_unit, formato_celdas_decimal)
                    worksheet.write(row, 10, line.quantity, formato_celdas_decimal)
                    worksheet.write(row, 11, uxb_id.name if uxb_id else '', formato_celdas_izquierda)
                    worksheet.write(row, 12, bultos, formato_celdas_decimal)
                    worksheet.write(row, 13, line.discount, formato_celdas_decimal)
                    worksheet.write(row, 14, line.price_subtotal, formato_celdas_decimal)
                    worksheet.write(row, 15, factura.company_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 16, line.product_id.categ_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 17, line.product_id.categ_id.parent_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 18, line.product_id.product_brand_id.name, formato_celdas_izquierda)
                    worksheet.write(row, 19, line.product_id.x_contract_id.name if line.product_id.x_contract_id else ' ', formato_celdas_izquierda)
                    worksheet.write(row, 20, line.product_id.x_subcontract_id.name if line.product_id.x_subcontract_id else ' ', formato_celdas_izquierda)
                    worksheet.write(row, 21, line.product_id.x_character_id.name if line.product_id.x_character_id else ' ', formato_celdas_izquierda)
                    worksheet.write(row, 22, line.product_id.x_property_id.name if line.product_id.x_property_id else ' ', formato_celdas_izquierda)
                    row += 1

        workbook.close()
        output.seek(0)
        # Codificar el archivo en base64
        archivo_excel = base64.b64encode(output.read())
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'reporte.factura.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {
                'default_archivo_excel': archivo_excel,
                'default_name': 'Reporte-de-Factura.xlsx',
            }
        }