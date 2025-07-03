from odoo import models, fields

class ReturnMove(models.Model):
    _name = 'return.move'

    name = fields.Char(string="Nombre", required=True, default="Remito de prueba")
    partner_id = fields.Many2one('res.partner', string="Cliente")
    sale_id = fields.Many2one()
    invoice_id = fields.Many2one()
    cause = fields.Selection()
    date = fields.Date()
    state = fields.Selection()
    move_lines = fields.One2many()

    


class ReturnMoveLine(models.Model):
    _name = 'return.move.line'

    name = fields.Char(string="Nombre", required=True, default="Remito de prueba")
    product_id = fields.Many2one()
    quantity = fields.Integer()
    uxb = fields.Integer()
    bultos = fields.Float()
    
    