# -*- coding: utf-8 -*-
from odoo import models, fields, _
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
from odoo.exceptions import AccessError, UserError, ValidationError
import logging, json
from datetime import date, datetime
from odoo.tools.misc import format_date, format_amount
from odoo.tools.float_utils import float_compare
_logger = logging.getLogger(__name__)

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