from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    executive_id = fields.Many2one('res.users',
        string="Ejecutivo de cuenta",copy=False)
    floor = fields.Char(string='Piso')
    apartment = fields.Char(string='Departamento')
