from odoo import models, fields, api


class WMSStockLocation(models.Model):
    _name = 'wms.stock.location'

    name = fields.Char(string="Ubicación")
    warehouse_id = fields.Many2one(string="Almacen", comodel_name="wms.warehouse")
    container_ids = fields.One2many(string="Contenedores", comodel_name="wms.container", inverse_name="location_id")
