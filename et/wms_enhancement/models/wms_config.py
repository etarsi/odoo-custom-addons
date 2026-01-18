from odoo import models, fields, api


class WMSProvider(models.Model):
    _name = 'wms.provider'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()

class WMSClient(models.Model):
    _name = 'wms.client'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()

class WMSTransport(models.Model):
    _name = 'wms.transport'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()


class WMSZone(models.Model):
    _name = 'wms.zone'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()

class WMSPosition(models.Model):
    _name = 'wms.position'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()

class WNSPrinter(models.Model):
    _name = 'wms.printer'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()

class WMSTag(models.Model):
    _name = 'wms.tag'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()

class WMSVehicle(models.Model):
    _name = 'wms.vehicle'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()

class WMSPickingRule(models.Model):
    _name = 'wms.picking.rule'
#     _description = 'wms_enhancement.wms_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()