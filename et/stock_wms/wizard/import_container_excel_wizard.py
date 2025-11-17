# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64, re
from io import BytesIO
from openpyxl import load_workbook


class ImportContainerExcelWizard(models.TransientModel):
    _name = 'import.container.excel.wizard'
    _description = 'Wizard: Importar Contenedores desde Excel'

    file = fields.Binary(string='Archivo Excel', required=True)
    nro_despacho = fields.Char(string='N° Despacho')
    fecha_llegada = fields.Date(string='ETA')

    # ----------------- HELPERS -----------------
    def _find_license_number(self, ws):
        """Busca 'LIC. 22508' en cualquier celda y devuelve '22508'."""
        max_row = ws.max_row
        max_col = ws.max_column
        for r in range(1, max_row + 1):
            for c in range(1, max_col + 1):
                val = ws.cell(row=r, column=c).value
                if not val:
                    continue
                text = str(val).upper()
                m = re.search(r'LIC\.\s*(\d+)', text)
                if m:
                    return m.group(1)
        return False

    def _normalize_code(self, value):
        """Convierte números/strings a código sin decimales tipo '56078'."""
        if value in (None, ''):
            return False
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return str(int(value))
        return str(value).strip()

    def _to_float(self, value):
        if value in (None, ''):
            return 0.0
        try:
            return float(value)
        except Exception:
            return 0.0

    def _extract_container_code(self, raw_text):
        """
        De algo como 'CONTAINER A#:JXLU4330628/A4250077459'
        devuelve 'JXLU4330628'.
        """
        if not raw_text:
            return False
        text = str(raw_text).strip()
        if ':' in text:
            text = text.split(':', 1)[1]
        if '/' in text:
            text = text.split('/', 1)[0]
        text = text.strip()
        return text or False

    # ----------------- IMPORT PRINCIPAL -----------------
    def import_data(self):
        self.ensure_one()

        if not self.file:
            raise UserError(_("Debe adjuntar un archivo de Excel."))
        try:
            data = base64.b64decode(self.file)
        except Exception as e:
            raise UserError(_("No se pudo decodificar el archivo.\nDetalle técnico: %s") % e)
        try:
            wb = load_workbook(BytesIO(data), data_only=True)
        except Exception as e:
            raise UserError(_("No se pudo leer el archivo Excel (.xlsx).\n"
                            "Asegúrese de que el archivo sea un .xlsx válido.\n"
                            "Detalle técnico: %s") % e)

        # Tomamos la hoja 'PACKING LIST' si existe, si no la activa
        sheet_name = 'PACKING LIST' if 'PACKING LIST' in wb.sheetnames else wb.sheetnames[0]
        ws = wb[sheet_name]

        max_row = ws.max_row
        max_col = ws.max_column

        # -------- 1) Detectar TODOS los headers y TODOS los CONTAINER --------
        header_rows = []     # filas donde está ITEM CODE / CTNS
        container_rows = []  # lista de dicts {'row': r, 'code': 'JXLU4330628'}

        for r in range(1, max_row + 1):
            row_vals_raw = [
                ws.cell(row=r, column=c).value
                for c in range(1, max_col + 1)
            ]
            row_text_upper = [
                str(v).strip().upper()
                for v in row_vals_raw if v not in (None, '')
            ]

            if not row_text_upper:
                continue

            # Header de bloque
            if 'ITEM CODE' in row_text_upper and 'CTNS' in row_text_upper:
                header_rows.append(r)

            # Fila CONTAINER A#/B#...
            if any('CONTAINER' in v for v in row_text_upper):
                cont_cell = next(
                    (v for v in row_vals_raw if v and 'CONTAINER' in str(v).upper()),
                    None
                )
                cont_code = self._extract_container_code(cont_cell) if cont_cell else False
                container_rows.append({'row': r, 'code': cont_code})

        if not header_rows or not container_rows:
            raise UserError(_("No se encontraron bloques de contenedor en el archivo."))

        # Usamos el PRIMER header para mapear columnas (todas tienen el mismo layout)
        header_row_idx = header_rows[0]
        header_row = [
            ws.cell(row=header_row_idx, column=c).value
            for c in range(1, max_col + 1)
        ]
        col_by_name = {}
        for idx, val in enumerate(header_row, start=1):
            if val:
                key = str(val).strip().upper()
                col_by_name[key] = idx

        def col(name):
            return col_by_name.get(name.upper())

        col_sb_code = col('SB CODE')
        col_ctns = col('CTNS')
        col_pcs = col('PCS')

        if not col_sb_code or not col_ctns or not col_pcs:
            raise UserError(_("No se encontraron las columnas 'SB CODE', 'CTNS' y/o 'PCS' en el encabezado."))

        # N° de licencia arriba: "PACKING LIST - LIC. 22508"
        license_number = self._find_license_number(ws)
        china_purchase = self.env['china.purchase'].search([], limit=1)

        created_container_ids = []

        # -------- 2) Recorrer CADA CONTENEDOR (A, B, ...) --------
        for cont in container_rows:
            cont_row = cont['row']
            cont_code = cont['code'] or '/'

            # Header correspondiente a este bloque = último header antes del CONTAINER
            header_for_block = None
            for h in header_rows:
                if h < cont_row:
                    header_for_block = h
                else:
                    break

            if not header_for_block:
                # Por seguridad, si no se encuentra header anterior, saltamos este bloque
                continue

            start_row = header_for_block + 1
            end_row = cont_row - 1

            # ---- Crear contenedor ----
            vals_container = {
                'name': cont_code,
                'license': license_number,
                'china_purchase': china_purchase.id if china_purchase else False,
                'eta': self.fecha_llegada if self.fecha_llegada else fields.Date.today(),
                'dispatch_number': self.nro_despacho if self.nro_despacho else False,
            }
            container = self.env['container'].create(vals_container)
            created_container_ids.append(container.id)

            # ---- Crear líneas del contenedor ----
            line_vals_to_create = []
            missing_codes = []

            for r in range(start_row, end_row + 1):
                sb_val = ws.cell(row=r, column=col_sb_code).value if col_sb_code else None
                sb_code = self._normalize_code(sb_val)
                if not sb_code:
                    # filas de totales parciales (solo números) se saltan solas
                    continue

                product = self.env['product.product'].search(
                    [('default_code', '=', sb_code)], limit=1
                )
                if not product:
                    missing_codes.append(sb_code)
                    continue

                qty_bultos = ws.cell(row=r, column=col_ctns).value if col_ctns else 0
                qty_cantidad = ws.cell(row=r, column=col_pcs).value if col_pcs else 0

                vals_line = {
                    'container': container.id,
                    'product_id': product.id,
                    'quantity_send': self._to_float(qty_cantidad),
                    'bultos': self._to_float(qty_bultos),
                    'quantity_picked': 0,
                }
                line_vals_to_create.append(vals_line)

            if missing_codes:
                missing_txt = ', '.join(sorted(set(missing_codes)))
                raise UserError(_(
                    "En el bloque del contenedor %s los siguientes 'SB CODE' "
                    "no se encontraron como productos en Odoo (default_code):\n%s"
                ) % (cont_code, missing_txt))

            for vals_line in line_vals_to_create:
                self.env['container.line'].create(vals_line)

        # -------- 3) Volver mostrando los contenedores creados --------
        if not created_container_ids:
            raise UserError(_("No se creó ningún contenedor desde el archivo."))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'container',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created_container_ids)],
            'target': 'current',
            'name': _('Contenedores Importados'),
        }

