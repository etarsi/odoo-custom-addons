from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class ClientPurchaseIntent(models.Model):
    _name = 'client.purchase.intent'

    sale_id = fields.Many2one('sale.order')
    sale_line_id = fields.Many2one('sale.order.line')
    product_id = fields.Many2one('product.product')
    quantity = fields.Integer()
    uxb = fields.Integer()
    bultos = fields.Float()
    