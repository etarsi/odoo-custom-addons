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
from calendar import monthrange
from pyafipws.iibb import IIBB
import logging
_logger = logging.getLogger(__name__)


COMPANY_IDS = [2, 3, 4] # Reemplazar con los IDs reales de las compañías a actualizar
USUARIO_ARBA = "30708077034"
CONTRASENA_ARBA = "Funtoys0205"
ARBA_PROD_URL = "https://dfe.arba.gov.ar/DomicilioElectronico/SeguridadCliente/dfeServicioConsulta.do"

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
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.vat:
                rec.update_iibb()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'vat' in vals:
            for rec in self:
                if rec.vat:
                    rec.update_iibb()
        return res

    def update_iibb(self):
        """Sugerir diario y cuenta para facturas de proveedor AFIP Import según CUIT."""
        _logger.warning("onchange_vat_iibb_agip_arba triggered for partner %s with VAT %s", self.name, self.vat)
        if not self.vat:
            return # Si no hay CUIT, no hacer nada
        _logger.warning("Procesando CUIT %s para partner %s", self.vat, self.name)
        cuit = ''.join(ch for ch in self.vat if ch.isdigit()) # Extraer solo dígitos del CUIT
        if len(cuit) != 11:
            raise ValidationError(_("El CUIT debe tener 11 dígitos. Por favor, ingrese un CUIT válido para el partner %s.") % self.name)
        #no agregar cuit duplicados en vat de contactos hijos
        if self.search([('vat', '=', self.vat), ('id', '!=', self.id)]):
            raise ValidationError(_("El CUIT %s ya existe en otro partner. Por favor, ingrese un CUIT único para el partner %s.") % (self.vat, self.name))
        #ACTUALIZAR AGIP
        self.udpdate_iibb_agip()
        self.update_iibb_arba()
            
    def udpdate_iibb_agip(self):
        """Actualizar diario y cuenta para facturas de proveedor AFIP Import según CUIT."""
        date_today = date.today()
        date_from = date(date_today.year, date_today.month, 1)
        date_to = date_from + relativedelta(months=1, days=-1)
        cuit = ''.join(ch for ch in (self.vat or '') if ch.isdigit())
        period_key = f"{date_today.month:02d}-{date_today.year}"
        tag_id = self.env['account.account.tag'].search([('name', '=', 'Ret/Perc IIBB AGIP')], limit=1)
        for company in COMPANY_IDS:
            arba_alicuotas = self.env['res.partner.arba_alicuot'].search([('partner_id','=',self.id), ('company_id','=',company), 
                                                                            ('from_date','=',date_from), ('to_date','=',date_to), ('tag_id','=',tag_id.id)], limit=1)
            if not arba_alicuotas:
                padron_iibb = self.env['ar.padron.iibb'].search([('cuit', '=', cuit), ('period', '=', period_key)], limit=1)
                if padron_iibb:
                    vals = {
                        'partner_id': self.id,
                        'company_id': company,
                        'tag_id': tag_id.id, #tag de alícuota general AGIP
                        'alicuota_percepcion': padron_iibb.perception_agip,
                        'alicuota_retencion': padron_iibb.retention_agip,
                        'from_date': date_from,
                        'to_date': date_to,
                    }
                    self.env['res.partner.arba_alicuot'].create(vals)
                
    def update_iibb_arba(self):
        self.ensure_one()
        date_today = date.today()
        date_from = date(date_today.year, date_today.month, 1)
        date_to = date_from + relativedelta(months=1, days=-1)
        cuit = ''.join(ch for ch in (self.vat or '') if ch.isdigit())
        period_key = f"{date_today.month:02d}-{date_today.year}"

        tag_id = self.env['account.account.tag'].search([('name', '=', 'Ret/Perc IIBB ARBA')], limit=1)
        if not tag_id:
            return

        padron_iibb = self.env['ar.padron.iibb'].search([
            ('cuit', '=', cuit),
            ('period', '=', period_key),
            ('arba_verified', '=', True),
        ], limit=1)

        data = None
        if padron_iibb:
            data = {
                'perception_arba': padron_iibb.perception_arba,
                'retention_arba': padron_iibb.retention_arba,
            }
        else:
            data = self.verificar_padron_iibb_arba(cuit, period_key)

        if not data:
            return

        #VALIDAR SI HAY ALÍCUOTAS ARBA, SI NO HAY, NO CREAR REGISTRO DE ALÍCUOTA (para evitar llenar la tabla con alícuotas 0)
        perception = data.get('perception_arba', 0.0) or 0.0
        retention = data.get('retention_arba', 0.0) or 0.0
        if perception == 0 and retention == 0:
            return
        
        sql = """
            INSERT INTO res_partner_arba_alicuot
                (partner_id, company_id, tag_id,
                    alicuota_percepcion, alicuota_retencion,
                    from_date, to_date,
                    create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
        """

        for company in COMPANY_IDS:
            existing = self.env['res.partner.arba_alicuot'].search([
                ('partner_id','=',self.id), 
                ('company_id','=',company), 
                ('from_date','=',date_from), 
                ('to_date','=',date_to), 
                ('tag_id','=',tag_id.id)
            ], limit=1)

            if not existing:
                self.env.cr.execute(sql, (
                    self.id,
                    company,
                    tag_id.id,
                    perception,
                    retention,
                    date_from,
                    date_to,
                    self.env.uid,
                    self.env.uid,
                ))
                create_by_sql = True
                if create_by_sql:
                    self.env['res.partner.arba_alicuot'].invalidate_cache() # Invalidar cache para que los cambios se reflejen inmediatamente en búsquedas posteriores

    def verificar_padron_iibb_arba(self, cuit, period_key):
        self.ensure_one()

        hoy = date.today()
        desde = hoy.replace(day=1)
        hasta = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])
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

        alicuota_percepcion = self._to_float_ar(iibb.AlicuotaPercepcion)
        alicuota_retencion = self._to_float_ar(iibb.AlicuotaRetencion)

        padron_model = self.env['ar.padron.iibb']
        existing = padron_model.search([
            ('cuit', '=', cuit),
            ('period', '=', period_key),
        ], limit=1)

        vals = {
            'cuit': cuit,
            'period': period_key,
            'perception_arba': alicuota_percepcion,
            'retention_arba': alicuota_retencion,
            'arba_verified': True,
        }

        if existing:
            existing.write(vals)
        else:
            vals.update({
                'perception_agip': 0.0,
                'retention_agip': 0.0,
            })
            padron_model.create(vals)

        if alicuota_percepcion == 0 and alicuota_retencion == 0:
            return None

        return {
            "perception_arba": alicuota_percepcion,
            "retention_arba": alicuota_retencion,
        }
    
    def _to_float_ar(self, value):
        """Convertir string numérico con formato argentino a float."""
        if isinstance(value, (int, float)):
            return float(value)
        if not value:
            return 0.0
        try:
            # Eliminar puntos de miles y reemplazar coma decimal por punto
            normalized = value.replace('.', '').replace(',', '.')
            return float(normalized)
        except ValueError:
            _logger.error("No se pudo convertir el valor '%s' a float", value)
            return 0.0