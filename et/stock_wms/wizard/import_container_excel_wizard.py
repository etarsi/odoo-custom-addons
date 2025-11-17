# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import xlrd  # Asegurate de tener xlrd instalado en el entorno

class ImportContainerExcelWizard(models.TransientModel):
    _name = 'import.container.excel.wizard'
    _description = 'Wizard: Importar Contenedores desde Excel'

    file = fields.Binary(string='Archivo Excel', required=True)
    nro_despacho = fields.Char(string='Número de Despacho', required=True)
    fecha_llegada = fields.Date(string='ETA')

    def import_data(self):
        self.ensure_one()

        if not self.file:
            raise UserError(_("Debe adjuntar un archivo de Excel."))

        # Contenedor desde el que se abre el wizard
        container = self.env['container'].browse(self.env.context.get('active_id'))
        if not container:
            raise UserError(_("Este asistente debe abrirse desde un contenedor."))

        # Actualizar datos generales del contenedor
        container.dispatch_number = self.nro_despacho
        if self.fecha_llegada:
            container.eta = self.fecha_llegada

        # Decodificar el binario
        try:
            data = base64.b64decode(self.file)
        except Exception as e:
            raise UserError(_("No se pudo decodificar el archivo.\nDetalle técnico: %s") % e)

        # Abrir libro Excel
        try:
            book = xlrd.open_workbook(file_contents=data)
        except Exception as e:
            raise UserError(_("No se pudo leer el archivo Excel.\n"
                              "Asegúrese de que sea un .xls/.xlsx válido.\n"
                              "Detalle técnico: %s") % e)

        sheet = book.sheet_by_index(0)

        if sheet.nrows <= 1:
            raise UserError(_("El archivo no contiene datos (solo encabezado)."))

        # --- ESTRUCTURA ASUMIDA DEL EXCEL ---
        # Fila 0 = encabezado, desde la fila 1 empiezan los datos
        # Columna 0: Código producto (default_code)
        # Columna 1: Cantidad enviada (quantity_send)
        # Columna 2: item_code
        # Columna 3: fake_code
        # Columna 4: bar_code
        # Columna 5: dun14_master
        # Columna 6: dun14_inner
        # Columna 7: dun14_display
        CODE_COL = 0
        QTY_COL = 1
        ITEM_COL = 2
        FAKE_COL = 3
        BAR_COL = 4
        DUNM_COL = 5
        DUNI_COL = 6
        DUND_COL = 7

        line_vals_to_create = []
        not_found_codes = []

        def _get_float(cell_value):
            if cell_value in (None, ''):
                return 0.0
            try:
                return float(cell_value)
            except Exception:
                return 0.0

        for row in range(1, sheet.nrows):
            raw_code = str(sheet.cell_value(row, CODE_COL)).strip()
            if not raw_code:
                # Fila vacía → la salteamos
                continue

            product = self.env['product.product'].search([('default_code', '=', raw_code)], limit=1)
            if not product:
                not_found_codes.append(raw_code)
                continue

            qty = _get_float(sheet.cell_value(row, QTY_COL))
            item_code = _get_float(sheet.cell_value(row, ITEM_COL)) if sheet.ncols > ITEM_COL else 0.0
            fake_code = _get_float(sheet.cell_value(row, FAKE_COL)) if sheet.ncols > FAKE_COL else 0.0
            bar_code = _get_float(sheet.cell_value(row, BAR_COL)) if sheet.ncols > BAR_COL else 0.0
            dun14_master = _get_float(sheet.cell_value(row, DUNM_COL)) if sheet.ncols > DUNM_COL else 0.0
            dun14_inner = _get_float(sheet.cell_value(row, DUNI_COL)) if sheet.ncols > DUNI_COL else 0.0
            dun14_display = _get_float(sheet.cell_value(row, DUND_COL)) if sheet.ncols > DUND_COL else 0.0

            vals = {
                'container': container.id,
                'product_id': product.id,
                'quantity_send': qty,
                'quantity_picked': 0,
                'item_code': item_code,
                'fake_code': fake_code,
                'bar_code': bar_code,
                'dun14_master': dun14_master,
                'dun14_inner': dun14_inner,
                'dun14_display': dun14_display,
            }
            line_vals_to_create.append(vals)

        if not_found_codes:
            # No creamos nada si hay productos que no existen en Odoo
            codes_txt = ', '.join(sorted(set(not_found_codes)))
            raise UserError(_("Los siguientes códigos no se encontraron como productos en Odoo:\n%s") % codes_txt)

        # Borramos líneas actuales del contenedor y cargamos las nuevas del Excel
        container.lines.unlink()
        for vals in line_vals_to_create:
            self.env['container.line'].create(vals)

        # Cerrar el wizard
        return {'type': 'ir.actions.act_window_close'}
