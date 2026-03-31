from odoo import models, fields, api, _
import requests
from odoo.exceptions import UserError, ValidationError


class ArPadronIibb(models.Model):
    _name = 'ar.padron.iibb'

    name = fields.Char(string='Nombre', required=True)
    cuit = fields.Char(string='CUIT', required=True)
    iibb_type = fields.Selection([('arba', 'ARBA'), ('agip', 'AGIP')], string='IIBB', required=True)
    perception = fields.Float(string='Percepción', required=True)
    retention = fields.Float(string='Retención', required=True)
    period = fields.Char(string='Período', required=True)
