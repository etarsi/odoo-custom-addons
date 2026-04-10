# -*- coding: utf-8 -*-
from odoo import models, fields, _, api
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
from odoo.exceptions import AccessError, UserError, ValidationError
import logging, json
from datetime import date, datetime
from odoo.tools.misc import format_date, format_amount
from odoo.tools.float_utils import float_compare
_logger = logging.getLogger(__name__)

COMPANY_IDS = [2, 3, 4] # Reemplazar con los IDs reales de las compañías a actualizar

class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'
    
    diario_prov_afip_import_id = fields.Selection(string='Diario Proveedor', selection=[
        ('lavalle', 'FACTURAS PROVEEDORES LAVALLE'),
        ('deposito', 'FACTURAS PROVEEDORES DEPOSITO'),
        ('smile', 'FACTURAS PROVEEDORES SMILES'),
    ], help='Seleccionar el diario para facturas de proveedor AFIP Import', default = 'lavalle')
    cuenta_prov_afip_import_id = fields.Many2one('account.account', string='Cuenta Proveedor', help='Seleccionar la cuenta para facturas de proveedor AFIP Import')
    mail_alternative = fields.Char(string='Email Alternativo', help='Email alternativo para envíos de comprobantes y notificaciones.')
    mail_alternative_b = fields.Char(string='Email Alternativo B', help='Segundo email alternativo para envíos de comprobantes y notificaciones.')
    

    def action_resumen_composicion(self):
        """Abrir facturas del cliente (y contactos hijos) en vista tree personalizada."""
        self.ensure_one()
        action = self.env.ref('account_enhancement.action_partner_invoices_tree').read()[0]
        # facturas cliente + NC cliente, solo publicadas; incluye partner y sus hijos
        action['domain'] = [
            ('move_type', 'in', ['out_invoice']),
            ('state', '=', 'posted'),
            ('partner_id', 'child_of', self.commercial_partner_id.id),
        ]
        # orden por fecha de factura (reciente primero)
        action['context'] = {
            'search_default_group_by_partner': 0,
            'search_default_open': 0,
            'default_move_type': 'out_invoice',
        }
        return action
    
    @api.onchange('vat')
    def onchange_vat_iibb_agip_arba(self):
        """Sugerir diario y cuenta para facturas de proveedor AFIP Import según CUIT."""
        if not self.vat:
            return # Si no hay CUIT, no hacer nada
        cuit = ''.join(ch for ch in self.vat if ch.isdigit()) # Extraer solo dígitos del CUIT
        if len(cuit) != 11:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Aviso"),
                    'message': _("Ingrese un CUIT válido."),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        #ACTUALIZAR AGIP
        self.udpdate_iibb_agip()
        self.update_iibb_arba()
            
    def udpdate_iibb_agip(self):
        """Actualizar diario y cuenta para facturas de proveedor AFIP Import según CUIT."""
        for company in COMPANY_IDS:
            date_today = date.today()
            period = f"{date_today.year}{date_today.month:02d}"
            date_from = date(date_today.year, date_today.month, 1)
            date_to = date_from + relativedelta(months=1, days=-1)
            arba_alicuotas = self.env['res.partner.arba_alicuot'].search([('partner_id','=',self.id), ('company_id','=',company), 
                                                                            ('from_date','=',date_from), ('to_date','=',date_to)], limit=1)
            if not arba_alicuotas:
                padron_iibb = self.env['ar.padron.iibb'].search([('cuit', '=', ''.join(ch for ch in (self.vat or '') if ch.isdigit())), 
                                                                    ('iibb_type', '=', 'agip'), ('period', '=', period)], limit=1)
                if padron_iibb:
                    vals = {
                        'partner_id': self.id,
                        'company_id': company,
                        'tag_id': 19, #tag de alícuota general AGIP
                        'alicuota_percepcion': padron_iibb.perception,
                        'alicuota_retencion': padron_iibb.retention,
                        'from_date': date_from,
                        'to_date': date_to,
                    }
                    self.env['res.partner.arba_alicuot'].create(vals)
                
    def update_iibb_arba(self):
        """Actualizar diario y cuenta para facturas de proveedor AFIP Import según CUIT de todos los partners."""
        partners = self.search([('vat', '!=', False)])
        for partner in partners:
            cuit = ''.join(ch for ch in (partner.vat or '') if ch.isdigit())
            if len(cuit) != 11:
                continue
            padron = self.env['ar.padron.iibb'].search([('cuit', '=', cuit), ('iibb_type', '=', 'arba')], limit=1)
            if padron:
                diario_key = padron.partner_id.diario_prov_afip_import_id or 'lavalle'
                cuenta = padron.partner_id.cuenta_prov_afip_import_id
                partner.diario_prov_afip_import_id = diario_key
                partner.cuenta_prov_afip_import_id = cuenta.id if cuenta else None
                

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
    arba_iibb_user = fields.Char(string="ARBA IIBB Usuario")
    arba_iibb_password = fields.Char(string="ARBA IIBB Password")
    arba_iibb_testing = fields.Boolean(string="ARBA IIBB Testing", default=False)

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

        user = self.arba_iibb_user or '30708077034'
        password = self.arba_iibb_password or 'Funtoys0205'
        url = ARBA_TEST_URL if self.arba_iibb_testing else ARBA_PROD_URL

        iibb = IIBB()
        iibb.Usuario = user
        iibb.Password = password
        iibb.Conectar(url=url)

        hoy = date(int(self.year), int(self.month), 1)
        desde = hoy.replace(day=1)
        hasta = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])

        tag_id = self.env['account.account.tag'].search([('name', '=', 'Ret/Perc IIBB ARBA')], limit=1)
        if not tag_id:
            raise UserError(_("No se encontró el tag 'Ret/Perc IIBB ARBA'. Por favor, cree este tag antes de ejecutar la consulta."))

        # Filtrá más si podés: customer_rank, company_type, etc.
        partners = self.env['res.partner'].search([
            ('active', '=', True),
            ('vat', '!=', False),
        ])

        _logger.warning(
            "Iniciando consulta ARBA IIBB para %s partners activos con período %s/%s",
            len(partners), self.month, self.year
        )

        arba_model = self.env['res.partner.arba_alicuot']

        # Traigo todos los existentes de una sola vez
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

        for idx, partner in enumerate(partners, start=1):
            cuit = self._get_partner_cuit_clean(partner)
            if not cuit or not cuit.isdigit() or len(cuit) != 11:
                errors.append("Partner %s tiene CUIT inválido: %s" % (partner.name, partner.vat))
                continue
            try:
                ok = iibb.ConsultarContribuyentes(
                    desde.strftime("%Y%m%d"),
                    hasta.strftime("%Y%m%d"),
                    cuit
                )
            except Exception as e:
                errors.append("Error al consultar ARBA para partner %s (CUIT %s): %s" % (partner.name, partner.vat, str(e)))
                continue

            if not ok:
                continue

            leido = iibb.LeerContribuyente()
            if not leido:
                continue

            alicuota_percepcion = self._to_float_ar(iibb.AlicuotaPercepcion)
            alicuota_retencion = self._to_float_ar(iibb.AlicuotaRetencion)
            
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
            if idx % 100 == 0:
                _logger.warning("ARBA IIBB procesados %s/%s partners", idx, len(partners))

        # Crear en lote
        if create_vals:
            #crear por las COMPANY_IDS para evitar problemas de multiempresa con reglas de acceso
            for company_id in COMPANY_IDS:
                for vals in create_vals:
                    vals['company_id'] = company_id
                    arba_model.create([vals])
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