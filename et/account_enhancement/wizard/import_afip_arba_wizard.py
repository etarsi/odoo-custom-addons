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
        for partner in partners:
            cuit = self._get_partner_cuit_clean(partner)
            if not cuit or not cuit.isdigit() or len(cuit) != 11:
                errors.append("Partner %s tiene CUIT inválido: %s" % (partner.name, partner.vat))
                continue
            _logger.info("Conexión a ARBA IIBB realizada. Con URL: %s | Testing: %s", url, self.arba_iibb_testing)
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
                errors.append("Error al consultar ARBA para partner %s (CUIT %s): %s" % (partner.name, partner.vat, iibb.MensajeError or "Error desconocido"))
                continue
            # para un solo CUIT, intentamos leer el contribuyente devuelto
            leido = iibb.LeerContribuyente()
            vals.update({"arba_numero_comprobante": iibb.NumeroComprobante or False, "arba_codigo_hash": iibb.CodigoHash or False})
            if leido:
                self.env['res.partner.arba.alicuot']


            else:
                vals["arba_error"] = "ARBA no devolvió contribuyente para el CUIT consultado."
                errors.append("Error al consultar ARBA para partner %s (CUIT %s): %s" % (partner.name, partner.vat, vals["arba_error"]))

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