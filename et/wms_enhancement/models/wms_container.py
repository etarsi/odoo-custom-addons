from odoo import models, fields, api


class WMSContainer(models.Model):
    _name = 'wms.container'

    name = fields.Char(string="Nombre")
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    location = fields.Many2one(string="Ubicación", comodel_name="wms.stock.location")
    quantity = fields.Integer(string="Cantidad")
    uxb = fields.Integer(string="UxB")
    
    # area = fields.Many2one(string="Area")
    # warehouse = fields.Many2one(string="Almacen")
    rubro = fields.Char(string="Rubro")
    
    
    
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100