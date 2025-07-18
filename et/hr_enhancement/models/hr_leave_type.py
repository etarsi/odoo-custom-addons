from odoo import models, fields, api

class TypeLicense(models.Model):
    _name = 'type.license'

    name = fields.Char(string="Nombre", required=True, help="Nombre del tipo de licencia")
    state = fields.Selection(selection=[
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
    ], string='Estado', required=True, default='active')
    description = fields.Text(string="Descripción", help="Descripción del tipo de licencia")