from odoo import models, fields, api


class PurchaseInherit(models.Model):
    _inherit = 'purchase.order'
    
    china_purchase = fields.Boolean('Compra china', default=False)

class PurchaseLineInherit(models.Model):
    _inherit = 'purchase.order.line'
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        for record in self:
            if record.product_id:
                record.product_uom = 1