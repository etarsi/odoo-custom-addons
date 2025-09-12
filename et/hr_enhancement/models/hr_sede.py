from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
from datetime import datetime

class HrSede(models.Model):
    _name = "hr.sede"
    _description = "Sede"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", required=True)
    active = fields.Boolean(string="Activo", default=True)
    direccion = fields.Char(string="Dirección")
    phone = fields.Char(string="Teléfono")
    departamento_ids = fields.Many2many('hr.department', string="Departamentos")
    
    def areas_laborales(self):
        self.ensure_one()
        return True