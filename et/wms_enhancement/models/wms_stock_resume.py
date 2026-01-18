from odoo import models, fields, api


class WMSStockResume(models.Model):
    _name = 'wms.stock.resume'

    name = fields.Char()
    product_id = fields.Many2one()
    receiving = fields.Integer()
    available = fields.Integer()
    prepared = fields.Integer()
    locked = fields.Integer()
    scrap = fields.Integer()
    inconsistency = fields.Integer()

    
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
