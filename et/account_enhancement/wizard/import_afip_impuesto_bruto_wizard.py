# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io
import re
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
    month = fields.Selection(
        selection=[(str(i), date(1900, i, 1).strftime('%B')) for i in range(1, 13)],
        string='Mes', required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    year = fields.Integer(
        string='Año', required=True,
        default=lambda self: fields.Date.today().year,
    )

    delimiter = fields.Char(string='Separador', default=';')
    cuit_index = fields.Integer(string='Indice CUIT', default=3)
    percepcion_index = fields.Integer(string='Indice Percepcion', default=7)
    retencion_index = fields.Integer(string='Indice Retencion', default=8)
    tag_id = fields.Integer(string='ID de Tag', default=19)
    # Compilar regex una vez (más rápido)
    _re_digits = re.compile(r"\D+")

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

    def import_data(self):
        self.ensure_one()
        # VALIDACIONES
        if not self.file:
            raise UserError(_("Debe adjuntar el TXT de AFIP."))
        #validar año valido
        if self.year < 2000 or self.year > 2100:
            raise UserError(_("El año ingresado no es válido."))
        #si añaden letra en el year
        if not isinstance(self.year, int):
            raise UserError(_("El año ingresado no es válido."))

        m = int(self.month)
        y = int(self.year)
        from_date = date(y, m, 1)
        to_date = date(y, m, monthrange(y, m)[1])  # FIX diciembre
        attachment = self.env['ir.attachment'].sudo()
        att = attachment.search([('res_model', '=', self._name), ('res_id', '=', self.id), ('res_field', '=', 'file')], order='id desc', limit=1)
        if not att:
            raise UserError(_("No se encontró el archivo adjunto."))
        path = att._full_path(att.store_fname)
        # 1) CUIT -> partner_id en O(1)
        rows = self.env['res.partner'].with_context(active_test=False).search_read(
            [('vat', '!=', False)],
            ['id', 'vat']
        )
        partner_by_cuit = {}
        for r in rows:
            c = self._norm_cuit(r.get('vat'))
            if c:
                partner_by_cuit[c] = r['id']

        # 2) Parse streaming y quedarnos con el último valor por partner
        delim = self.delimiter or ';'
        cuit_i = int(self.cuit_index)
        perc_i = int(self.percepcion_index)
        ret_i = int(self.retencion_index)
        max_idx = max(cuit_i, perc_i, ret_i)
        rates_by_partner = {}
        #notificar cuando habre el archivo
        with open(path, 'rb') as fb:
            f = io.TextIOWrapper(fb, encoding='latin-1', errors='replace', newline='')
            for i, line in enumerate(f, start=1):
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
        f.close()

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

        # 4) Update/Create masivo usando temp table
        now = fields.Datetime.now()
        uid = self.env.uid
        rows = []
        for pid, (perc, ret) in rates_by_partner.items():
            for company_id in COMPANY_IDS:
                rows.append((pid, self.tag_id, company_id, from_date, to_date, perc, ret, uid, now, uid, now))

        # 1) Crear temp table
        cr = self.env.cr
        cr.execute("""DROP TABLE IF EXISTS tmp_agip_alicuot""")
        cr.execute("""
            CREATE TEMP TABLE tmp_agip_alicuot (
                partner_id integer,
                tag_id integer,
                company_id integer,
                from_date date,
                to_date date,
                alicuota_percepcion numeric,
                alicuota_retencion numeric,
                create_uid integer,
                create_date timestamp,
                write_uid integer,
                write_date timestamp
            ) ON COMMIT DROP
        """)

        # 2) Cargar temp table en bulk
        execute_values(cr, """
            INSERT INTO tmp_agip_alicuot
            (partner_id, tag_id, company_id, from_date, to_date,
            alicuota_percepcion, alicuota_retencion,
            create_uid, create_date, write_uid, write_date)
            VALUES %s
        """, rows, page_size=10000)

        # 3) UPDATE masivo: actualiza todos los existentes
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

        # 4) INSERT masivo: inserta solo los que no existen
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
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Importación completada',
                'message': 'Se importaron las alícuotas de impuestos brutos correctamente.',
                'type': 'success',
                'sticky': True,
                'timeout': 12000,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }