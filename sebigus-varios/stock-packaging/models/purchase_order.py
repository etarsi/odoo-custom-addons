from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
            
    def get_bultos(self):
        for order in self:      
            for line in order.order_line:      
                 if line.product_packaging_qty:
                    if not line.product_packaging_id :
                        if line.product_id.packaging_ids and order.state in ['draft']: # and (line.product_uom_qty == 0 or not line.product_uom_qty):
                            line.write(
                                {
                                    'product_qty': int(line.product_id.packaging_ids[0].qty * line.product_packaging_qty),
                                    'product_packaging_id': line.product_id.packaging_ids[0],
                                })

