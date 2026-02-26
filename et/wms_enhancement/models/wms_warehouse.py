from odoo import models, fields, api


class WMSWarehouse(models.Model):
    _name = 'wms.warehouse'

    name = fields.Char(string="Almacen")
    location_ids = fields.One2many(string="Ubicaciones", comodel_name="wms.stock.location", inverse_name="warehouse_id")
