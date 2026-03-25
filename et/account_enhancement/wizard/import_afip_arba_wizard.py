# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date
from calendar import monthrange

from pyafipws.iibb import IIBB
import logging
_logger = logging.getLogger(__name__)


ARBA_TEST_URL = "https://dfe.test.arba.gov.ar/DomicilioElectronico/SeguridadCliente/dfeServicioConsulta.do"
ARBA_PROD_URL = "https://dfe.arba.gov.ar/DomicilioElectronico/SeguridadCliente/dfeServicioConsulta.do"
COMPANY_IDS = [2, 3, 4] #SEBIGUS, BECHAR, FUNTOYS

class ImportAfipArbaWizard(models.TransientModel):
    _name = 'import.afip.arba.wizard'
    _description = 'Wizard: Importar Alicuotas AFIP ARBA'

    # ----------------- ORIGEN -----------------
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
    arba_iibb_user = fields.Char(string="ARBA IIBB Usuario")
    arba_iibb_password = fields.Char(string="ARBA IIBB Password")
    arba_iibb_testing = fields.Boolean(string="ARBA IIBB Testing", default=True)

    def _get_partner_cuit_clean(self, partner_id):
        self.ensure_one()
        vat = partner_id.vat or ""
        vat = vat.replace("-", "").replace(" ", "")
        if vat.upper().startswith("AR"):
            vat = vat[2:]
        return vat

    def action_consultar_arba_iibb(self):
        self.ensure_one()

        arba_iibb_user = '30708077034' # Usuario de prueba de ARBA para testing
        arba_iibb_password = 'Funtoys0205' # Password de prueba de ARBA para testing
        iibb = IIBB()
        iibb.Usuario = arba_iibb_user
        iibb.Password = arba_iibb_password
        url = ARBA_PROD_URL
        iibb.Conectar(url=url)
        hoy = self.month and self.year and date(int(self.year), int(self.month), 1)
        desde = hoy.replace(day=1)
        hasta = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])
        # Todos los clientes activos
        partners = self.env['res.partner'].search([('active', '=', True), ('vat', '!=', False)])
        errors = []
        tag_id = self.env['account.account.tag'].search([('name', '=', 'Ret/Perc IIBB ARBA')], limit=1)
        if not tag_id:
            raise UserError(_("No se encontró el tag 'Ret/Perc IIBB ARBA'. Por favor, cree este tag antes de ejecutar la consulta."))
        create=0
        update=0
        for partner in partners:
            cuit = self._get_partner_cuit_clean(partner)
            if not cuit or not cuit.isdigit() or len(cuit) != 11:
                errors.append("Partner %s tiene CUIT inválido: %s" % (partner.name, partner.vat))
                continue
            ok = iibb.ConsultarContribuyentes(
                desde.strftime("%Y%m%d"),
                hasta.strftime("%Y%m%d"),
                cuit
            )
            # limpiar resultados previos
            vals = {
                "alicuota_percepcion": 0.0,
                "alicuota_retencion": 0.0,
                "partner_id": False,
                "tag_id": tag_id.id,
                "from_date": desde,
                "to_date": hasta,
            }
            if not ok:
                errors.append("Error al consultar ARBA para partner %s (CUIT %s): %s" % (partner.name, partner.vat, iibb.MensajeError or "Error desconocido"))
                continue
            # para un solo CUIT, intentamos leer el contribuyente devuelto
            leido = iibb.LeerContribuyente()
            vals.update({"arba_numero_comprobante": iibb.NumeroComprobante or False, "arba_codigo_hash": iibb.CodigoHash or False})
            if leido:
                exist_alicuota =self.env['res.partner.arba_alicuot'].search([('from_date', '=', desde), ('to_date', '=', hasta),
                                                                                ('partner_id', '=', partner.id), ('tag_id', '=', tag_id.id)], limit=1)
                if not exist_alicuota:
                    vals.update({
                        "alicuota_percepcion": float((iibb.AlicuotaPercepcion or '0').replace(",", ".")),
                        "alicuota_retencion": float((iibb.AlicuotaRetencion or '0').replace(",", ".")),
                        "partner_id": partner.id,
                    })
                    self.env['res.partner.arba_alicuot'].create(vals)
                    create += 1
                else:
                    exist_alicuota.write({
                        "alicuota_percepcion": float((iibb.AlicuotaPercepcion or '0').replace(",", ".")),
                        "alicuota_retencion": float((iibb.AlicuotaRetencion or '0').replace(",", ".")),
                    })
                    update += 1
            else:
                errors.append("Error al consultar ARBA para partner %s (CUIT %s): %s" % (partner.name, partner.vat, "No se devolvió información del contribuyente"))
                continue
        if create == 0 and update == 0 and errors:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Consulta ARBA"),
                    "message": "No se crearon ni actualizaron alícuotas para el período %s/%s. Errores:\n\n%s" % (self.month, self.year, "\n".join(errors)),
                    "type": "warning",
                    "sticky": True,
                }
            }

        elif create > 0 or update > 0 and errors:
             return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Consulta ARBA"),
                    "message": f"Se crearon {create} alícuotas y se actualizaron {update} alícuotas para el período {self.month}/{self.year}. Sin embargo, se encontraron algunos errores:\n\n" + "\n".join(errors),
                    "type": "warning",
                    "sticky": True,
                }
            }

        elif create > 0 or update > 0 and not errors:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Consulta ARBA"),
                    "message": f"Se crearon {create} alícuotas y se actualizaron {update} alícuotas para el período {self.month}/{self.year}.",
                    "type": "success",
                    "sticky": True,
                }
            }