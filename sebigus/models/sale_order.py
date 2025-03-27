from odoo import tools, models, fields, api, _


class ActionTest(models.Model):
    _inherit = "sale.order"

    def cargar_showroom(self):
        return {
            'name': 'Showroom',
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url' : "sebigus/sebigus/pedido/?pedido_id=%s" % self.id
        }

class SaleOrderLineExt(models.Model):
    _inherit = 'sale.order.line'  

    product_categ_id = fields.Many2one(related = 'product_id.product_tmpl_id.categ_id', string='Product Category')
    product_demand_qty = fields.Integer(string='Demanda')