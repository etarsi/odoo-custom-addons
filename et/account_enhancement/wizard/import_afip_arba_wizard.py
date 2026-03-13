# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date
from calendar import monthrange

from pyafipws.iibb import IIBB


ARBA_TEST_URL = "https://dfe.test.arba.gov.ar/DomicilioElectronico/SeguridadCliente/dfeServicioConsulta.do"
ARBA_PROD_URL = "https://dfe.arba.gov.ar/DomicilioElectronico/SeguridadCliente/dfeServicioConsulta.do"


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

    def _get_partner_cuit_clean(self):
        self.ensure_one()
        vat = '30707176284' # CUIT de prueba de ARBA para testing
        vat = vat.replace("-", "").replace(" ", "")
        if vat.upper().startswith("AR"):
            vat = vat[2:]
        return vat

    def action_consultar_arba_iibb(self):
        self.ensure_one()

        arba_iibb_user = '20267565393'
        arba_iibb_password = '99999'

        cuit = self._get_partner_cuit_clean()
        if not cuit or not cuit.isdigit() or len(cuit) != 11:
            raise UserError(_("El partner debe tener un CUIT válido de 11 dígitos en VAT."))

        hoy = self.month and self.year and date(int(self.year), int(self.month), 1)
        desde = hoy.replace(day=1)
        hasta = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])

        iibb = IIBB()
        iibb.Usuario = arba_iibb_user
        iibb.Password = arba_iibb_password

        url = ARBA_TEST_URL if self.arba_iibb_testing else ARBA_PROD_URL
        iibb.Conectar(url=url)

        ok = iibb.ConsultarContribuyentes(
            desde.strftime("%Y%m%d"),
            hasta.strftime("%Y%m%d"),
            cuit
        )

        # limpiar resultados previos
        vals = {
            "arba_alicuota_percepcion": 0.0,
            "arba_alicuota_retencion": 0.0,
            "arba_grupo_percepcion": False,
            "arba_grupo_retencion": False,
            "arba_numero_comprobante": False,
            "arba_codigo_hash": False,
            "arba_error": False,
            "arba_xml_response": iibb.XmlResponse or False,
        }

        if not ok:
            vals["arba_error"] = "La operación devolvió False. Excepción: %s | Código: %s | Mensaje: %s" % (
                iibb.Excepcion or "",
                iibb.CodigoError or "",
                iibb.MensajeError or "",
            )
            raise UserError(_(vals["arba_error"]))

        if iibb.Excepcion:
            vals["arba_error"] = "Error interno: %s\n%s" % (iibb.Excepcion or "", iibb.Traceback or "")
            raise UserError(_(vals["arba_error"]))

        if iibb.CodigoError:
            vals["arba_error"] = "ARBA devolvió error %s: %s" % (iibb.CodigoError, iibb.MensajeError or "")
            vals["arba_numero_comprobante"] = iibb.NumeroComprobante or False
            vals["arba_codigo_hash"] = iibb.CodigoHash or False
            raise UserError(_(vals["arba_error"]))

        # para un solo CUIT, intentamos leer el contribuyente devuelto
        leido = iibb.LeerContribuyente()

        vals.update({
            "arba_numero_comprobante": iibb.NumeroComprobante or False,
            "arba_codigo_hash": iibb.CodigoHash or False,
        })

        if leido:
            vals.update({
                "arba_alicuota_percepcion": float(iibb.AlicuotaPercepcion or 0.0),
                "arba_alicuota_retencion": float(iibb.AlicuotaRetencion or 0.0),
                "arba_grupo_percepcion": iibb.GrupoPercepcion or False,
                "arba_grupo_retencion": iibb.GrupoRetencion or False,
                "arba_error": False,
            })
            raise UserError(_("Consulta ARBA realizada correctamente.\n\nAlic. Percepción: %s\nAlic. Retención: %s\nGrupo Percepción: %s\nGrupo Retención: %s") % (
                vals["arba_alicuota_percepcion"],
                vals["arba_alicuota_retencion"],
                vals["arba_grupo_percepcion"],
                vals["arba_grupo_retencion"],
            ))

        else:
            vals["arba_error"] = "ARBA no devolvió contribuyente para el CUIT consultado."

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Consulta ARBA"),
                "message": _("Consulta realizada correctamente."),
                "type": "success",
                "sticky": False,
            }
        }