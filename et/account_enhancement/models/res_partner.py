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
        for company in COMPANY_IDS:
            arba_alicuotas = self.env['res.partner.arba_alicuot'].search([('partner_id','=',self.id), ('company_id','=',company), 
                                                                            ('from_date','=',date_from), ('to_date','=',date_to)], limit=1)
            if not arba_alicuotas:
                padron_iibb = self.env['ar.padron.iibb'].search([('cuit', '=', cuit), ('period', '=', period_key)], limit=1)
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
        date_today = date.today()
        date_from = date(date_today.year, date_today.month, 1)
        date_to = date_from + relativedelta(months=1, days=-1)
        cuit = ''.join(ch for ch in (self.vat or '') if ch.isdigit())
        period_key = f"{date_today.month:02d}-{date_today.year}"
        for company in COMPANY_IDS:
            arba_alicuotas = self.env['res.partner.arba_alicuot'].search([('partner_id','=',self.id), ('company_id','=',company), 
                                                                            ('from_date','=',date_from), ('to_date','=',date_to)], limit=1)
            if not arba_alicuotas:
                padron_iibb = self.env['ar.padron.iibb'].search([('cuit', '=', cuit), ('period', '=', period_key), ('arba_verified', '=', True)], limit=1)
                if padron_iibb:
                    vals = {
                        'partner_id': self.id,
                        'company_id': company,
                        'tag_id': 20, #tag de alícuota general ARBA
                        'alicuota_percepcion': padron_iibb.perception_arba,
                        'alicuota_retencion': padron_iibb.retention_arba,
                        'from_date': date_from,
                        'to_date': date_to,
                    }
            else:
                padron_iibb = self.verificar_padron_iibb_arba(cuit, period_key)
                if padron_iibb:
                    vals = {
                        'partner_id': self.id,
                        'company_id': company,
                        'alicuota_percepcion': padron_iibb.get('perception_arba', arba_alicuotas.alicuota_percepcion),
                        'alicuota_retencion': padron_iibb.get('retention_arba', arba_alicuotas.alicuota_retencion),
                        'from_date': date_from,
                        'to_date': date_to,
                    }
            self.env['res.partner.arba_alicuot'].create(vals)
                
    def verificar_padron_iibb_arba(self, cuit, period_key):
        hoy = date.today()
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

        alicuota_percepcion = self._to_float_ar(iibb.AlicuotaPercepcion)
        alicuota_retencion = self._to_float_ar(iibb.AlicuotaRetencion)

        #CREAR ar.padron.iibb con arba_verified = True para no volver a consultar a ARBA por ese cuit en esa gestión
        self.env['ar.padron.iibb'].create({
            'cuit': cuit,
            'period': period_key,
            'alicuota_percepcion': alicuota_percepcion,
            'alicuota_retencion': alicuota_retencion,
            'arba_verified': True,
        })
    
        if alicuota_percepcion == 0 or alicuota_retencion == 0:
            return None

        return {
            "perception_arba": alicuota_percepcion,
            "retention_arba": alicuota_retencion,
        }