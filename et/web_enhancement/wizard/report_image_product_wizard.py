from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import xlsxwriter
from . import excel
import os
import tempfile


class ReportImageProductWizard(models.TransientModel):
    _name = 'report.image.product.wizard'
    _description = 'Reporte de Imagen de Producto'



    def action_generar_excel(self):
        self.ensure_one()

        domain = []
        domain.append(('sale_ok', '=', True))
        domain.append(('website_published', '=', True))
        products = self.env['product.template'].search(domain)
        if not products:
            raise ValidationError("No se encontraron productos para generar el reporte.")

        # Archivo temporal (reduce RAM vs BytesIO + in_memory)
        tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        tmp_path = tmp.name
        tmp.close()

        workbook = xlsxwriter.Workbook(tmp_path, {'constant_memory': True})
        worksheet = workbook.add_worksheet('Fotos Productos')

        # Columnas
        worksheet.set_column(0, 0, 20)
        worksheet.set_column(1, 2, 40)
        worksheet.set_column(3, 3, 10)
        worksheet.set_column(4, 4, 25)
        worksheet.set_column(5, 6, 15)


        # Formatos
        formato_encabezado = excel.formato_encabezado(workbook)
        formato_celdas_izquierda = excel.formato_celda_izquierda(workbook)
        formato_celdas_derecha = excel.formato_celda_derecha(workbook)
        formato_celdas_decimal = excel.formato_celda_decimal(workbook)

        # Encabezados
        headers = ['CÓDIGO','PRODUCTO','CANT. IMAGENES']
        for col, h in enumerate(headers):
            worksheet.write(0, col, h, formato_encabezado)

        row = 1
        for product in products:
            worksheet.write(row, 0, product.default_code, formato_celdas_izquierda)
            worksheet.write(row, 1, product.name, formato_celdas_izquierda)
            worksheet.write(row, 2, len(product.gallery_image_ids) if product.gallery_image_ids else 0, formato_celdas_derecha)
            row += 1
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
            'name': 'reporte_imagen_producto.xlsx',
            'type': 'binary',
            'datas': archivo_excel,
            'store_fname': 'reporte_imagen_producto.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }