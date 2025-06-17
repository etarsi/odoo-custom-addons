from odoo import models, fields, api


class PurchaseInherit(models.Model):
    _inherit = 'purchase.order'
    
    china_purchase = fields.Boolean('Compra china', default=False)