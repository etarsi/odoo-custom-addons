from odoo import models, fields, api


class WMSArea(models.Model):
    _name = 'wms.area'

    name = fields.Char()
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    
    
    
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
