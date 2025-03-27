from odoo import models, fields, api
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    active = fields.Boolean(default=True)

    @api.constrains('order_line')
    def _check_repeated_products(self):
        for order in self:
            product_counts = {}
            for line in order.order_line:
                product = line.product_id
                if product in product_counts:
                    product_counts[product] += 1
                else:
                    product_counts[product] = 1

            # CHEQUEAR PRODUCTOS REPETIDOS
            repeated_products = [product for product, count in product_counts.items() if count > 1]
            if repeated_products:
                product_names = ', '.join([product.display_name for product in repeated_products])
                raise UserError(f"Los siguientes productos están repetidos en las líneas de la orden: {product_names}")
