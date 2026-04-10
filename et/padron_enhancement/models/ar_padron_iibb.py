from odoo import models, fields, api, _
import requests
from odoo.exceptions import UserError, ValidationError


class ArPadronIibb(models.Model):
    _name = 'ar.padron.iibb'
    _description = 'Padrón de IIBB-AGIP-ARBA'

    partner_name = fields.Char(string='Nombre del Cliente', store=True)
    cuit = fields.Char(string='CUIT', store=True)
    perception_agip = fields.Float(string='Percepción AGIP')
    perception_arba = fields.Float(string='Percepción ARBA')
    retention_agip = fields.Float(string='Retención AGIP')
    retention_arba = fields.Float(string='Retención ARBA')
    arba_verified = fields.Boolean(string='Verificado en ARBA', default=False)
    period = fields.Char(string='Período', required=True)

    _sql_constraints = [
        (
            'ar_padron_iibb_unique_cuit_period',
            'unique(cuit, period)',
            'Ya existe un registro para ese CUIT y período.'
        ),
    ]

    @api.constrains('cuit')
    def _check_cuit(self):
        for rec in self:
            cuit = ''.join(ch for ch in (rec.cuit or '') if ch.isdigit())
            if not cuit or len(cuit) != 11:
                raise ValidationError(_("El CUIT debe tener exactamente 11 dígitos."))