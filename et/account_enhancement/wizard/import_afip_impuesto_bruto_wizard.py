# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io
import os
import re
import time
import logging
from datetime import date
from calendar import monthrange
from psycopg2.extras import execute_values

_logger = logging.getLogger(__name__)

COMPANY_IDS = [2, 3, 4]


class ImportAfipImpuestoBrutoWizard(models.TransientModel):
    _name = 'import.afip.impuesto.bruto.wizard'
    _description = 'Wizard: Importar AFIP (Impuestos Brutos)'

    file = fields.Binary('Archivo', required=True, attachment=True)
    filename = fields.Char('Nombre de archivo')

    month = fields.Selection(
        selection=[(str(i), date(1900, i, 1).strftime('%B')) for i in range(1, 13)],
        string='Mes',
        required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    year = fields.Integer(
        string='Año',
        required=True,
        default=lambda self: fields.Date.today().year,
    )

    delimiter = fields.Char(string='Separador', default=';')
    cuit_index = fields.Integer(string='Indice CUIT', default=3)
    percepcion_index = fields.Integer(string='Indice Percepcion', default=7)
    retencion_index = fields.Integer(string='Indice Retencion', default=8)
    tag_id = fields.Integer(string='ID de Tag', default=19)

    _re_digits = re.compile(r"\D+")

    # ----------------- HELPERS -----------------

    def _norm_cuit(self, v):
        if not v:
            return False
        return self._re_digits.sub("", str(v)) or False

    def _to_float(self, v):
        if v in (None, '', False):
            return 0.0
        try:
            s = str(v).strip()
            # "1.234,56" -> "1234.56"
            if s.count(',') == 1:
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '.')
            return float(s)
        except Exception:
            return 0.0

    def _get_or_create_attachment(self):
        """Asegura que exista un ir.attachment vinculado al campo file del wizard."""
        self.ensure_one()
        if not self.file:
            raise UserError(_("Debe adjuntar el TXT de AFIP."))

        Attachment = self.env['ir.attachment'].sudo()

        att = Attachment.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('res_field', '=', 'file'),
        ], order='id desc', limit=1)

        if att:
            return att

        # Crear attachment explícitamente (robusto)
        att = Attachment.create({
            'name': self.filename or 'padron_afip.txt',
            'type': 'binary',
            'datas': self.file,  # ya viene en base64
            'res_model': self._name,
            'res_id': self.id,
            'res_field': 'file',
            'mimetype': 'text/plain',
        })
        return att

    def _open_attachment_binary(self, att):
        """
        Devuelve (fb, close_needed) donde fb es un file-like binario.
        - Si está en filestore: open(path, 'rb')
        - Si está en DB: BytesIO(base64decode(datas))
        """
        if att.store_fname:
            path = att._full_path(att.store_fname)
            return open(path, 'rb'), True

        # Fallback: guardado en DB
        if not att.datas:
            raise UserError(_("El adjunto no tiene contenido (datas vacío)."))
        return io.BytesIO(base64.b64decode(att.datas)), False

    # ----------------- IMPORT PRINCIPAL -----------------

    def import_data(self):
        self.ensure_one()

        # Validación de año (Integer ya valida tipo, pero dejamos rango)
        if self.year < 2000 or self.year > 2100:
            raise UserError(_("El año ingresado no es válido."))

        m = int(self.month)
        y = int(self.year)
        from_date = date(y, m, 1)
        to_date = date(y, m, monthrange(y, m)[1])

        t0 = time.monotonic()
        _logger.info("AFIP IIBB: inicio wizard id=%s", self.id)

        # 0) Attachment seguro
        att = self._get_or_create_attachment()
        fb, close_fb = self._open_attachment_binary(att)

        # 1) CUIT -> partner_id (O(1))
        partner_rows = self.env['res.partner'].with_context(active_test=False).search_read(
            [('vat', '!=', False), ('type', '=', 'contact')],
            ['id', 'vat']
        )
        partner_by_cuit = {}
        for r in partner_rows:
            c = self._norm_cuit(r.get('vat'))
            if c:
                partner_by_cuit[c] = r['id']

        _logger.info("AFIP IIBB: partners con CUIT=%s (%.2fs)",
                     len(partner_by_cuit), time.monotonic() - t0)

        # 2) Parse streaming
        delim = (self.delimiter or ';')
        cuit_i = int(self.cuit_index)
        perc_i = int(self.percepcion_index)
        ret_i = int(self.retencion_index)
        max_idx = max(cuit_i, perc_i, ret_i)

        rates_by_partner = {}  # partner_id -> (perc, ret)
        processed = 0
        matched = 0
        log_each = 200000

        try:
            f = io.TextIOWrapper(fb, encoding='latin-1', errors='replace', newline='')
            for i, line in enumerate(f, start=1):
                processed = i
                if not line:
                    continue
                parts = line.strip().split(delim)
                if len(parts) <= max_idx:
                    continue

                cuit = self._norm_cuit(parts[cuit_i])
                if not cuit:
                    continue

                pid = partner_by_cuit.get(cuit)
                if not pid:
                    continue

                rates_by_partner[pid] = (self._to_float(parts[perc_i]), self._to_float(parts[ret_i]))
                matched += 1

                if i % log_each == 0:
                    _logger.info("AFIP IIBB: lineas=%s matches=%s partners_matcheados=%s (%.2fs)",
                                 i, matched, len(rates_by_partner), time.monotonic() - t0)
        finally:
            try:
                f.detach()
            except Exception:
                pass
            if close_fb:
                fb.close()

        _logger.info("AFIP IIBB: parse fin lineas=%s partners_matcheados=%s (%.2fs)",
                     processed, len(rates_by_partner), time.monotonic() - t0)

        if not rates_by_partner:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin coincidencias',
                    'message': 'No se encontraron CUIT del padrón en contactos.',
                    'type': 'warning',
                    'sticky': True,
                    'timeout': 12000,
                    'next': {'type': 'ir.actions.act_window_close'}
                }
            }

        # 3) Preparar filas para temp table (partner x company)
        now = fields.Datetime.now()
        uid = self.env.uid
        sql_rows = []
        for pid, (perc, ret) in rates_by_partner.items():
            for company_id in COMPANY_IDS:
                sql_rows.append((pid, self.tag_id, company_id, from_date, to_date, perc, ret, uid, now, uid, now))

        cr = self.env.cr

        # 4) Temp table
        cr.execute("DROP TABLE IF EXISTS tmp_agip_alicuot")
        cr.execute("""
            CREATE TEMP TABLE tmp_agip_alicuot (
                partner_id integer,
                tag_id integer,
                company_id integer,
                from_date date,
                to_date date,
                alicuota_percepcion numeric(16,6),
                alicuota_retencion numeric(16,6),
                create_uid integer,
                create_date timestamp,
                write_uid integer,
                write_date timestamp
            ) ON COMMIT DROP
        """)

        # Bulk insert temp
        execute_values(cr, """
            INSERT INTO tmp_agip_alicuot
            (partner_id, tag_id, company_id, from_date, to_date,
             alicuota_percepcion, alicuota_retencion,
             create_uid, create_date, write_uid, write_date)
            VALUES %s
        """, sql_rows, page_size=10000)

        # Índice y estadísticas sobre la temp (muy útil en producción)
        cr.execute("""
            CREATE INDEX tmp_agip_alicuot_match_idx
            ON tmp_agip_alicuot (partner_id, tag_id, company_id, from_date, to_date)
        """)
        cr.execute("ANALYZE tmp_agip_alicuot")

        _logger.info("AFIP IIBB: temp cargada rows=%s (%.2fs)", len(sql_rows), time.monotonic() - t0)

        # 5) UPDATE masivo
        cr.execute("""
            UPDATE res_partner_arba_alicuot t
            SET
                alicuota_percepcion = s.alicuota_percepcion,
                alicuota_retencion  = s.alicuota_retencion,
                write_uid = s.write_uid,
                write_date = s.write_date
            FROM tmp_agip_alicuot s
            WHERE t.partner_id = s.partner_id
              AND t.tag_id = s.tag_id
              AND t.company_id = s.company_id
              AND t.from_date = s.from_date
              AND t.to_date = s.to_date
        """)
        updated = cr.rowcount

        _logger.info("AFIP IIBB: UPDATE ok updated=%s (%.2fs)", updated, time.monotonic() - t0)

        # 6) INSERT masivo (solo faltantes)
        cr.execute("""
            INSERT INTO res_partner_arba_alicuot
            (partner_id, tag_id, company_id, from_date, to_date,
             alicuota_percepcion, alicuota_retencion,
             create_uid, create_date, write_uid, write_date)
            SELECT
                s.partner_id, s.tag_id, s.company_id, s.from_date, s.to_date,
                s.alicuota_percepcion, s.alicuota_retencion,
                s.create_uid, s.create_date, s.write_uid, s.write_date
            FROM tmp_agip_alicuot s
            WHERE NOT EXISTS (
                SELECT 1
                FROM res_partner_arba_alicuot t
                WHERE t.partner_id = s.partner_id
                  AND t.tag_id = s.tag_id
                  AND t.company_id = s.company_id
                  AND t.from_date = s.from_date
                  AND t.to_date = s.to_date
            )
        """)
        inserted = cr.rowcount

        _logger.info("AFIP IIBB: INSERT ok inserted=%s (%.2fs)", inserted, time.monotonic() - t0)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Importación completada',
                'message': "Se actualizaron y crearon las alicuotas de impuestos brutos según el padrón de AFIP.\n",
                'type': 'success',
                'sticky': True,
                'timeout': 20000,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
