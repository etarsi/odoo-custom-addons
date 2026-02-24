from odoo import models, fields, api


class WMSProductLot(models.Model):
    _name = 'wms.product.lot'

    name = fields.Char(string="Nombre")
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    lot_name = fields.Char(string="Lote")