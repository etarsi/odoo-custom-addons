# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError
from datetime import date
from calendar import monthrange

from pyafipws.iibb import IIBB
import logging
_logger = logging.getLogger(__name__)

ARBA_TEST_URL = "https://dfe.test.arba.gov.ar/DomicilioElectronico/SeguridadCliente/dfeServicioConsulta.do"
ARBA_PROD_URL = "https://dfe.arba.gov.ar/DomicilioElectronico/SeguridadCliente/dfeServicioConsulta.do"
COMPANY_IDS = [2, 3, 4]  # SEBIGUS, BECHAR, FUNTOYS


class ImportAfipArbaWizard(models.TransientModel):
    _name = 'import.afip.arba.wizard'
    _description = 'Wizard: Importar Alicuotas AFIP ARBA'

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

    def _get_partner_cuit_clean(self, partner):
        self.ensure_one()
        vat = (partner.vat or "").replace("-", "").replace(" ", "")
        if vat.upper().startswith("AR"):
            vat = vat[2:]
        return vat

    def _to_float_ar(self, value):
        if value in (False, None, ''):
            return 0.0
        value = str(value).strip()
        if ',' in value and '.' in value:
            value = value.replace('.', '').replace(',', '.')
        elif ',' in value:
            value = value.replace(',', '.')
        try:
            return float(value)
        except Exception:
            return 0.0

    def action_consultar_arba_iibb(self):
        self.ensure_one()

        hoy = date(int(self.year), int(self.month), 1)
        desde = hoy.replace(day=1)
        hasta = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])
        period = "%02d-%04d" % (hoy.month, hoy.year)
        tag_id = self.env['account.account.tag'].search([('name', '=', 'Ret/Perc IIBB ARBA')], limit=1)
        if not tag_id:
            raise UserError(_("No se encontró el tag 'Ret/Perc IIBB ARBA'. Por favor, cree este tag antes de ejecutar la consulta."))
        # Filtrá más si podés: customer_rank, company_type, etc.
        partners = self.env['res.partner'].search([('active', '=', True), ('vat', '!=', False)])
        arba_model = self.env['res.partner.arba_alicuot']
        existing_records = arba_model.search([
            ('from_date', '=', desde),
            ('to_date', '=', hasta),
            ('tag_id', '=', tag_id.id),
            ('partner_id', 'in', partners.ids),
            ('company_id', 'in', COMPANY_IDS),
        ])
        existing_map = {
            (rec.partner_id.id, rec.company_id.id): rec
            for rec in existing_records
        }

        errors = []
        create_vals = []
        to_update = []
        create_count = 0
        update_count = 0

        #VERIFICAR QUE TODO EN AR.PADRON.IBB ESTE ARBA_VERIFIED = TRUE DE LA GESTION SELECCIONADA SI HAY UNO SOLO QUE NO ESTE VERIFICADO, USER ERROR QUE DIGA QUE FALTA VER
        self.env.cr.execute("""
            SELECT cuit FROM ar_padron_iibb
            WHERE period = %s
            AND arba_verified IS NOT TRUE
        """, (period,))
        not_verified_cuits = [row[0] for row in self.env.cr.fetchall()]
        if not_verified_cuits:
            raise UserError(_(
                "No se pueden importar alícuotas de ARBA porque hay CUITs en el padrón de IIBB que no han sido verificados. "
                "Por favor, ejecuta el proceso de verificación para el período %s-%s antes de importar."
            ) % (self.month, self.year))

        for partner in partners:
            cuit = self._get_partner_cuit_clean(partner)
            if not cuit or not cuit.isdigit() or len(cuit) != 11:
                errors.append("Partner %s tiene CUIT inválido: %s" % (partner.name, partner.vat))
                continue
            
            ar_padron_iibb = self.env['ar.padron.iibb'].search([('cuit', '=', cuit), ('period', '=', period), ('arba_verified', '=', True)], limit=1)
            if not ar_padron_iibb:
                errors.append("Partner %s con CUIT %s no encontrado en el padrón de AFIP IIBB" % (partner.name, cuit))
                continue

            alicuota_percepcion = self._to_float_ar(ar_padron_iibb.perception_arba)
            alicuota_retencion = self._to_float_ar(ar_padron_iibb.retention_arba)
            
            if alicuota_percepcion == 0 and alicuota_retencion == 0:
                continue

            for company_id in COMPANY_IDS:
                key = (partner.id, company_id)
                existing = existing_map.get(key)
                if existing:
                    if (existing.alicuota_percepcion != alicuota_percepcion or
                        existing.alicuota_retencion != alicuota_retencion):
                        to_update.append((existing, {
                            "alicuota_percepcion": alicuota_percepcion,
                            "alicuota_retencion": alicuota_retencion,
                        }))
                else:
                    create_vals.append({
                        "partner_id": partner.id,
                        "company_id": company_id,
                        "tag_id": tag_id.id,
                        "from_date": desde,
                        "to_date": hasta,
                        "alicuota_percepcion": alicuota_percepcion,
                        "alicuota_retencion": alicuota_retencion,
                    })

        # Crear en lote
        if create_vals:
            arba_model.with_context(allowed_company_ids=COMPANY_IDS).sudo().create(create_vals)
            create_count = len(create_vals)

        # Actualizar existentes
        for rec, vals in to_update:
            rec.write(vals)
        update_count = len(to_update)

        if create_count == 0 and update_count == 0 and errors:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Consulta ARBA"),
                    "message": "No se crearon ni actualizaron alícuotas para el período %s/%s. Errores:\n\n%s"
                               % (self.month, self.year, "\n".join(errors[:50])),
                    "type": "warning",
                    "sticky": True,
                }
            }

        elif (create_count > 0 or update_count > 0) and errors:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Consulta ARBA"),
                    "message": (
                        f"Se crearon {create_count} alícuotas y se actualizaron {update_count} alícuotas "
                        f"para el período {self.month}/{self.year}. Sin embargo, hubo errores:\n\n"
                        + "\n".join(errors[:50])
                    ),
                    "type": "warning",
                    "sticky": True,
                }
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Consulta ARBA"),
                "message": (
                    f"Se crearon {create_count} alícuotas y se actualizaron {update_count} alícuotas "
                    f"para el período {self.month}/{self.year}."
                ),
                "type": "success",
                "sticky": True,
            }
        }