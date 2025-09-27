from odoo import models, fields, api, _

class ChinaPurchase(models.Model):
    _name = 'china.purchase'

    name = fields.Char()
    partner_id = fields.Many2one('res.partner', string='Proveedor')
    state = fields.Selection(selection=[('draft', 'Borrador'), ('confirmed', 'Confirmado'), ('closed', 'Cerrado')], default="draft")
    order_line = fields.One2many('china.purchase.line', 'china_purchase', string="Líneas de Compra")


    def action_confirm(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'confirmed'

                for line in record.order_line:
                    line.add_enelagua_stock()
    


class ChinaPurchaseLine(models.Model):
    _name = 'china.purchase.line'

    name = fields.Char()
    china_purchase = fields.Many2one('china.purchase', string='Compra China')
    product_id = fields.Many2one('product.product', string='Producto')
    quantity = fields.Integer('Cantidad Comprada')
    quantity_received = fields.Integer('Cantidad Recibida')
    uxb = fields.Integer('UxB')
    bultos = fields.Float('Bultos', compute="_compute_bultos")



    @api.depends('quantity')
    def _compute_bultos(self):
        for record in self:
            record.bultos = record.quantity / record.uxb


    def add_enelagua_stock(self):
        for record in self:
            stock_erp = self.env['stock.erp'].search([('product_id', '=', record.product_id.id)])

            if stock_erp:
                stock_erp.enelagua_unidades = record.quantity
                stock_erp.comprado_unidades = record.quantity
            
            if not stock_erp:
                vals = {}
                vals['product_id'] = record.product_id.id
                vals['uxb'] = record.uxb
                vals['fisico_unidades'] = 0
                vals['enelagua_unidades'] = record.quantity
                vals['entregable_unidades'] = 0
                vals['comprado_unidades'] = record.quantity

                self.env['stock.erp'].create(vals)
