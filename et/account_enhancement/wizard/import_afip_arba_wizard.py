# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError
from datetime import date
from dateutil.relativedelta import relativedelta
from calendar import monthrange

from pyafipws.iibb import IIBB
import logging
_logger = logging.getLogger(__name__)

ARBA_PROD_URL = "https://dfe.arba.gov.ar/DomicilioElectronico/SeguridadCliente/dfeServicioConsulta.do"
COMPANY_IDS = [2, 3, 4]  # SEBIGUS, BECHAR, FUNTOYS
USUARIO_ARBA = "30708077034"
CONTRASENA_ARBA = "Funtoys0205"


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
        tag_id_agip = self.env['account.account.tag'].search([('name', '=', 'Ret/Perc IIBB AGIP')], limit=1)
        if not tag_id_agip:
            raise UserError(_("No se encontró el tag 'Ret/Perc IIBB AGIP'. Por favor, cree este tag antes de ejecutar la consulta."))
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
                consultar_arba = self.verificar_padron_iibb_arba(cuit, period)
                if not consultar_arba:
                    errors.append("Partner %s con CUIT %s no encontrado en el padrón de AFIP IIBB" % (partner.name, cuit))
                    continue
                else:
                    alicuota_percepcion = self._to_float_ar(consultar_arba.get('perception_arba'))
                    alicuota_retencion = self._to_float_ar(consultar_arba.get('retention_arba'))
            else:
                alicuota_percepcion = self._to_float_ar(ar_padron_iibb.perception_arba)
                alicuota_retencion = self._to_float_ar(ar_padron_iibb.retention_arba)
            
            if alicuota_percepcion == 0 and alicuota_retencion == 0:
                continue

            for company_id in COMPANY_IDS:
                self.udpdate_iibb_agip(partner, tag_id_agip, company_id, desde, hasta, ar_padron_iibb)
                key = (partner.id, company_id)
                existing = existing_map.get(key)
                if not existing:
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
                        f"para el período {self.month}-{self.year}. Sin embargo, hubo errores:\n\n"
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
                    f"para el período {self.month}-{self.year}."
                ),
                "type": "success",
                "sticky": True,
            }
        }
        
    def verificar_padron_iibb_arba(self, cuit, period_key):
        self.ensure_one()

        hoy = date(int(self.year), int(self.month), 1)
        desde = hoy.replace(day=1)
        hasta = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])
        period_key = "%02d-%04d" % (hoy.month, hoy.year)
        iibb = IIBB()
        iibb.Usuario = USUARIO_ARBA
        iibb.Password = CONTRASENA_ARBA
        iibb.Conectar(url=ARBA_PROD_URL)
        
        try:
            ok = iibb.ConsultarContribuyentes(
                desde.strftime("%Y%m%d"),
                hasta.strftime("%Y%m%d"),
                cuit
            )
        except Exception as e:
            _logger.error("Error consultando ARBA para CUIT %s: %s", cuit, str(e))
            return None
        
        if not ok:
            return None
        
        leido = iibb.LeerContribuyente()
        if not leido:
            return None        
        
        #CREAR ar.padron.iibb con arba_verified = True para no volver a consultar a ARBA por ese cuit en esa gestión
        self.env['ar.padron.iibb'].create({
            'cuit': cuit,
            'period': period_key,
            'perception_agip': 0.0,
            'retention_agip': 0.0,
            'perception_arba': self._to_float_ar(iibb.AlicuotaPercepcion),
            'retention_arba': self._to_float_ar(iibb.AlicuotaRetencion),
            'arba_verified': True,
        })

        return {
            "perception_agip": 0.0,
            "retention_agip": 0.0,
            "perception_arba": self._to_float_ar(iibb.AlicuotaPercepcion),
            "retention_arba": self._to_float_ar(iibb.AlicuotaRetencion),
        }
        
    def udpdate_iibb_agip(self, partner, tag_id_agip, company_id, desde, hasta, ar_padron_iibb):
        """Actualizar diario y cuenta para facturas de proveedor AFIP Import según CUIT."""
        arba_alicuotas = self.env['res.partner.arba_alicuot'].search([('partner_id','=',partner.id), ('company_id','=', company_id), 
                                                                        ('from_date','=',desde), ('to_date','=',hasta), ('tag_id','=', tag_id_agip.id)], limit=1)
        if not arba_alicuotas:
            if ar_padron_iibb:
                vals = {
                    'partner_id': partner.id,
                    'company_id': company_id,
                    'tag_id': tag_id_agip.id,
                    'alicuota_percepcion': ar_padron_iibb.perception_agip,
                    'alicuota_retencion': ar_padron_iibb.retention_agip,
                    'from_date': desde,
                    'to_date': hasta,
                }
                self.env['res.partner.arba_alicuot'].create(vals)