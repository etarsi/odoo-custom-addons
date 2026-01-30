from odoo import models, fields, api


class TmsCompany(models.Model):
    _name = 'tms.company'
    _description = 'Compañía de Transporte'

    name = fields.Char(string='Descripción', required=True)
    code = fields.Char(string='Código', required=True)
    active = fields.Boolean(string='Activo', default=True)