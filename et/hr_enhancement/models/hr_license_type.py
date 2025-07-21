from odoo import models, fields, api

class hrLicenseType(models.Model):
    _name = 'hr.license.type'
    _description = 'Tipo de Licencia'
    
    name = fields.Char('Nombre', required=True)
    description = fields.Text('Descripción')
    active = fields.Boolean('Activo', default=True)
    code = fields.Char('Código', required=True, help='Código único para identificar el tipo de licencia')