# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import base64
import re
from io import BytesIO
from datetime import datetime, date, timedelta
import logging
_logger = logging.getLogger(__name__)

COMPANY_IDS = [2, 3, 4]  # IDs de compañías donde se aplicará la alícuota

class ImportAfipImpuestoBrutoWizard(models.TransientModel):
    _name = 'import.afip.impuesto.bruto.wizard'
    _description = 'Wizard: Importar AFIP (Impuestos Brutos)'

    file = fields.Binary('Archivo', required=True)
    month = fields.Selection(
        selection=[(str(i), date(1900, i, 1).strftime('%B')) for i in range(1, 13)],
        string='Mes',
        required=True,
        default=lambda self: str(datetime.now().month),
    )
    year = fields.Integer(
        string='Año',   
        required=True,
        default=lambda self: datetime.now().year,
    )
    #PARAMETROS SETEADOS
    delimiter = fields.Char(string='Separador', default=';')
    cuit_index = fields.Integer(string='Indice CUIT', default=3)
    percepcion_index = fields.Integer(string='Indice Percepcion', default=7)
    retencion_index = fields.Integer(string='Indice Retencion', default=8)
    tag_id = fields.Integer(string='ID de Tag', default=19)

    # ----------------- HELPERS -----------------
    def _norm_cuit(self, v):
        # Igual idea que ya usás :contentReference[oaicite:5]{index=5}
        if not v:
            return False
        digits = re.sub(r"\D", "", str(v))
        return digits or False

    def _to_float(self, v):
        # Similar al helper que ya tenés :contentReference[oaicite:6]{index=6}
        if v in (None, '', False):
            return 0.0
        try:
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip()
            # Normalización común: "1.234,56" -> "1234.56"
            if s.count(',') == 1:
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '.')
            return float(s)
        except Exception:
            return 0.0

    def _decode_text(self, raw):
        # AGIP suele venir latin-1; fallback por las dudas
        try:
            return raw.decode('latin-1')
        except Exception:
            return raw.decode('utf-8', errors='replace')

    # ---------------- IMPORT PRINCIPAL ----------------
    def import_data(self):
        self.ensure_one()

        if not self.file:
            raise UserError(_("Debe adjuntar el TXT de AFIP."))

        raw = base64.b64decode(self.file)
        text = self._decode_text(raw)

        # 1) Armar un mapa CUIT -> partner_id de manera eficiente (sin loop por fila)
        partners = self.env['res.partner'].search([('vat', '!=', False)])
        _logger.info(f"Contactos con CUIT en Odoo: {len(partners)}")

        # 2) Parsear TXT y quedarnos solo con coincidencias
        delim = self.delimiter or ';'
        vals = {}
        for i, line in enumerate(text.splitlines()):
            _logger.info(f"Procesando línea {i+1}")
            if not line:
                continue
            parts = line.strip().split(delim)
            max_idx = max(self.cuit_index, self.percepcion_index, self.retencion_index)
            if len(parts) <= max_idx:
                continue
            cuit = self._norm_cuit(parts[self.cuit_index])
            if not cuit:
                continue
            partner_id = None  
            for p in partners:
                if self._norm_cuit(p.vat) == cuit:
                    partner_id = p.id
                    break
            if not partner_id:
                continue
            # 3) Preparar valores para inserción/actualización
            for company_id in COMPANY_IDS:
                vals = {
                    'partner_id': partner_id,
                    'tag_id': self.tag_id,
                    'company_id': company_id,  # Asumimos la primera compañía; ajustar si es necesario
                    'alicuota_percepcion': self._to_float(parts[self.percepcion_index]),
                    'alicuota_retencion': self._to_float(parts[self.retencion_index]),
                    #from_date y to_date para el mes/año seleccionado solo debe ser Fecha
                    'from_date': datetime(self.year, int(self.month), 1).date(),
                    'to_date': (datetime(self.year, int(self.month) % 12 + 1, 1) - timedelta(days=1)).date(),
                }
                
                ali_cuota = self.env['res.partner.arba.alicuot'].search([
                    ('partner_id', '=', partner_id),
                    ('tag_id', '=', self.tag_id),
                    ('company_id', '=', company_id),
                    ('from_date', '=', vals['from_date']),
                    ('to_date', '=', vals['to_date']),
                ], limit=1)
    
                if ali_cuota:
                    ali_cuota.write({
                        'alicuota_percepcion': vals['alicuota_percepcion'],
                        'alicuota_retencion': vals['alicuota_retencion'],
                    })
                else:
                    self.env['res.partner.arba.alicuot'].create(vals)

        # 5) Mostrar resultado (líneas)
        response = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Importación Completa',
                'message': 'La importación se realizó correctamente.',
                'type': 'info',
                'sticky': False,
                'timeout': 20000,
                'next': {'type': 'ir.actions.act_window_close' }
            }
        }
        return response