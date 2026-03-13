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
                
                record.create_transfer()
    
    
    def create_transfer(self):
        for record in self:      

            ### TRANSFER CREATION
            if record.transfer_id:
                continue

            transfer_vals = {
                'operation_type':'ingoing',
                'partner_id':record.partner_id.id,
                'partner_address_id':record.partner_id.id,
                'state': 'pending',
            }

            transfer_id = self.env['wms.transfer'].create(transfer_vals)
            transfer_lines_list = []
            for line in record.order_line:
               qty_demand = line.quantity
                   
               if line.product_id:
                   transfer_line = {
                       'transfer_id': transfer_id.id,
                       'product_id': line.product_id.id,
                       'state': 'pending',
                       'invoice_state': 'no',
                       'uxb': line.product_packaging_id.qty or False,
                       'qty_demand': qty_demand,
                    }

                   transfer_lines_list.append(transfer_line)
            
            self.env['wms.transfer.line'].create(transfer_lines_list)

            record.transfer_id = transfer_id.id



class ChinaPurchaseLine(models.Model):
    _name = 'china.purchase.line'

    name = fields.Char()
    china_purchase = fields.Many2one('china.purchase', string='Compra China')
    product_id = fields.Many2one('product.product', string='Producto')
    quantity = fields.Integer('Cantidad Comprada')
    quantity_received = fields.Integer('Cantidad Recibida')
    uxb = fields.Integer('UxB')
    bultos = fields.Float('Bultos', compute="_compute_bultos")

    quantity_to_add = fields.Integer('Cantidad a Aumentar')


    @api.depends('quantity')
    def _compute_bultos(self):
        for record in self:
            if record.uxb:
                record.bultos = record.quantity / record.uxb
            else:
                record.bultos = 0


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

    def add_quantity_to_stock(self):
        for record in self:
            stock_erp = self.env['stock.erp'].search([('product_id', '=', record.product_id.id)])

            if stock_erp:
                stock_erp.enelagua_unidades += record.quantity_to_add

                record.quantity += record.quantity_to_add

                record.quantity_to_add = 0

            if not stock_erp:
                vals = {}
                vals['product_id'] = record.product_id.id
                vals['uxb'] = record.product_id.packaging_ids[0].qty or 1,
                vals['fisico_unidades'] = 0
                vals['enelagua_unidades'] = record.quantity
                vals['entregable_unidades'] = 0
                vals['comprado_unidades'] = record.quantity

                self.env['stock.erp'].create(vals)