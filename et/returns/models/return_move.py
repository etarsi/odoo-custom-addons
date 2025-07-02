from odoo import models, fields

class ReturnMove(models.Model):
    _name = 'return.move'

    name = fields.Char(string="Nombre", required=True, default="Remito de prueba")


class ReturnMoveLine(models.Model):
    _name = 'return.move.line'

    name = fields.Char(string="Nombre", required=True, default="Remito de prueba")

    