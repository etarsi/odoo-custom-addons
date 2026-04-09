from odoo import models, fields, api, _
import requests
from odoo.exceptions import UserError, ValidationError


class ArPadronIibb(models.Model):
    _name = 'ar.padron.iibb'

    partner_id = fields.Many2one('res.partner', string='Cliente')
    partner_name = fields.Char(string='Nombre del Cliente', store=True)
    cuit = fields.Char(string='CUIT', store=True)
    iibb_type = fields.Selection([('arba', 'ARBA'), ('agip', 'AGIP')], string='IIBB', required=True)
    perception = fields.Float(string='Percepción', required=True)
    retention = fields.Float(string='Retención', required=True)
    period = fields.Char(string='Período', required=True)

    _sql_constraints = [
        (
            'ar_padron_iibb_unique_cuit_type_period',
            'unique(cuit, iibb_type, period)',
            'Ya existe un registro para ese CUIT, tipo de IIBB y período.'
        ),
    ]

    @api.constrains('cuit')
    def _check_cuit(self):
        for rec in self:
            cuit = ''.join(ch for ch in (rec.cuit or '') if ch.isdigit())
            if not cuit or len(cuit) != 11:
                raise ValidationError(_("El CUIT debe tener exactamente 11 dígitos."))