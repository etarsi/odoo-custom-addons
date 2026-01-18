from odoo import models, fields, api


class WMSInventoryAdjustment(models.Model):
    _name = 'wms.inventory.adjustment'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()