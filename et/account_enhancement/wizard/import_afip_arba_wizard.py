# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError
from datetime import date
from calendar import monthrange
from pyafipws.iibb import IIBB
import logging

_logger = logging.getLogger(__name__)

ARBA_PROD_URL = "https://dfe.arba.gov.ar/DomicilioElectronico/SeguridadCliente/dfeServicioConsulta.do"
COMPANY_IDS = [2, 3, 4]
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

    def _consultar_arba_cuits_faltantes(self, missing_cuits, period, desde, hasta):
        """
        Consulta ARBA solo para CUITs faltantes y devuelve:
        {
            '20123456789': {
                'perception_arba': 1.5,
                'retention_arba': 2.0,
            },
            ...
        }
        Además crea/actualiza ar.padron.iibb como caché.
        """
        self.ensure_one()

        result = {}
        if not missing_cuits:
            return result

        iibb = IIBB()
        iibb.Usuario = USUARIO_ARBA
        iibb.Password = CONTRASENA_ARBA
        iibb.Conectar(url=ARBA_PROD_URL)

        padron_model = self.env['ar.padron.iibb']

        for cuit in missing_cuits:
            try:
                ok = iibb.ConsultarContribuyentes(
                    desde.strftime("%Y%m%d"),
                    hasta.strftime("%Y%m%d"),
                    cuit
                )
            except Exception as e:
                _logger.error("Error consultando ARBA para CUIT %s: %s", cuit, str(e))
                continue

            if not ok:
                continue

            leido = iibb.LeerContribuyente()
            if not leido:
                continue

            perception_arba = self._to_float_ar(iibb.AlicuotaPercepcion)
            retention_arba = self._to_float_ar(iibb.AlicuotaRetencion)

            result[cuit] = {
                'perception_arba': perception_arba,
                'retention_arba': retention_arba,
            }

            existing_padron = padron_model.search([
                ('cuit', '=', cuit),
                ('period', '=', period),
            ], limit=1)

            vals_padron = {
                'cuit': cuit,
                'period': period,
                'perception_arba': perception_arba,
                'retention_arba': retention_arba,
                'arba_verified': True,
            }

            if existing_padron:
                existing_padron.write(vals_padron)
            else:
                vals_padron.update({
                    'perception_agip': 0.0,
                    'retention_agip': 0.0,
                })
                padron_model.create(vals_padron)

        return result

    def action_consultar_arba_iibb(self):
        self.ensure_one()

        hoy = date(int(self.year), int(self.month), 1)
        desde = hoy.replace(day=1)
        hasta = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])
        period = "%02d-%04d" % (hoy.month, hoy.year)

        tag_arba = self.env['account.account.tag'].search([
            ('name', '=', 'Ret/Perc IIBB ARBA')
        ], limit=1)
        if not tag_arba:
            raise UserError(_("No se encontró el tag 'Ret/Perc IIBB ARBA'."))

        tag_agip = self.env['account.account.tag'].search([
            ('name', '=', 'Ret/Perc IIBB AGIP')
        ], limit=1)
        if not tag_agip:
            raise UserError(_("No se encontró el tag 'Ret/Perc IIBB AGIP'."))

        partners = self.env['res.partner'].search([
            ('active', '=', True),
            ('vat', '!=', False),
        ])

        # 1) Normalizar partners por CUIT
        partners_by_cuit = {}
        invalid_partners = []

        for partner in partners:
            cuit = self._get_partner_cuit_clean(partner)
            if not cuit or not cuit.isdigit() or len(cuit) != 11:
                invalid_partners.append("Partner %s tiene CUIT inválido: %s" % (partner.name, partner.vat))
                continue
            partners_by_cuit.setdefault(cuit, self.env['res.partner'])
            partners_by_cuit[cuit] |= partner

        cuits = list(partners_by_cuit.keys())

        if not cuits:
            raise UserError(_("No hay partners activos con CUIT válido."))

        # 2) Buscar padrón en una sola consulta
        padron_records = self.env['ar.padron.iibb'].search([
            ('cuit', 'in', cuits),
            ('period', '=', period),
        ])
        padron_map = {rec.cuit: rec for rec in padron_records}

        # 3) Consultar ARBA solo para CUITs faltantes
        missing_cuits = [cuit for cuit in cuits if cuit not in padron_map]
        arba_online_map = self._consultar_arba_cuits_faltantes(missing_cuits, period, desde, hasta)

        # refrescar mapa con lo recién creado/actualizado
        if missing_cuits:
            new_padron_records = self.env['ar.padron.iibb'].search([
                ('cuit', 'in', missing_cuits),
                ('period', '=', period),
            ])
            for rec in new_padron_records:
                padron_map[rec.cuit] = rec

        # 4) Traer existentes ARBA/AGIP en una sola consulta
        all_partner_ids = partners.ids
        existing_alicuotas = self.env['res.partner.arba_alicuot'].search([
            ('partner_id', 'in', all_partner_ids),
            ('company_id', 'in', COMPANY_IDS),
            ('from_date', '=', desde),
            ('to_date', '=', hasta),
            ('tag_id', 'in', [tag_arba.id, tag_agip.id]),
        ])

        existing_map = {
            (rec.partner_id.id, rec.company_id.id, rec.tag_id.id): rec
            for rec in existing_alicuotas
        }

        create_vals = []
        errors = list(invalid_partners)

        for cuit, partner_recs in partners_by_cuit.items():
            padron = padron_map.get(cuit)

            if not padron:
                errors.append("No se encontró padrón para CUIT %s" % cuit)
                continue

            agip_per = self._to_float_ar(getattr(padron, 'perception_agip', 0.0))
            agip_ret = self._to_float_ar(getattr(padron, 'retention_agip', 0.0))
            arba_per = self._to_float_ar(getattr(padron, 'perception_arba', 0.0))
            arba_ret = self._to_float_ar(getattr(padron, 'retention_arba', 0.0))

            for partner in partner_recs:
                for company_id in COMPANY_IDS:
                    # AGIP
                    key_agip = (partner.id, company_id, tag_agip.id)
                    if key_agip not in existing_map and not (agip_per == 0 and agip_ret == 0):
                        create_vals.append({
                            'partner_id': partner.id,
                            'company_id': company_id,
                            'tag_id': tag_agip.id,
                            'alicuota_percepcion': agip_per,
                            'alicuota_retencion': agip_ret,
                            'from_date': desde,
                            'to_date': hasta,
                        })

                    # ARBA
                    key_arba = (partner.id, company_id, tag_arba.id)
                    if key_arba not in existing_map and not (arba_per == 0 and arba_ret == 0):
                        create_vals.append({
                            'partner_id': partner.id,
                            'company_id': company_id,
                            'tag_id': tag_arba.id,
                            'alicuota_percepcion': arba_per,
                            'alicuota_retencion': arba_ret,
                            'from_date': desde,
                            'to_date': hasta,
                        })

        create_count = 0
        if create_vals:
            self.env['res.partner.arba_alicuot'].with_context(
                allowed_company_ids=COMPANY_IDS
            ).sudo().create(create_vals)
            create_count = len(create_vals)

        if create_count == 0 and errors:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Consulta ARBA/AGIP"),
                    "message": _(
                        "No se crearon alícuotas para el período %s-%s.\n\n%s"
                    ) % (self.month, self.year, "\n".join(errors[:50])),
                    "type": "warning",
                    "sticky": True,
                }
            }

        if create_count > 0 and errors:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Consulta ARBA/AGIP"),
                    "message": _(
                        "Se crearon %s alícuotas para el período %s-%s.\n\nAdemás hubo errores:\n%s"
                    ) % (create_count, self.month, self.year, "\n".join(errors[:50])),
                    "type": "warning",
                    "sticky": True,
                }
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Consulta ARBA/AGIP"),
                "message": _("Se crearon %s alícuotas para el período %s-%s.") % (
                    create_count, self.month, self.year
                ),
                "type": "success",
                "sticky": True,
            }
        }