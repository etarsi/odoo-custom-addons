from odoo import models, fields, api


class WMSPreselection(models.Model):
    _name = 'wms.preselection'

    name = fields.Char(string="Nombre")
    date = fields.Date(string="Fecha Pedido")
    partner_id = fields.Many2one(string="Cliente", comodel_name="res.partner")
    line_ids = fields.One2many(string="Líneas de Preselección", comodel_name="wms.preselection.line", inverse_name="preselection_id")
    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")
    item_ids = fields.Many2many(string="Rubros", comodel_name="product.category", compute="_compute_item_ids", store=True)
    bultos_count = fields.Float(string="Bultos Totales", compute="_compute_bultos_count", store=True)
    lines_count = fields.Integer(string="Cantidad Líneas", compute="_compute_lines_count", store=True)
    state = fields.Selection(string="Estado", selection=[
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancel', 'Cancelado'),
        ('closed', 'Cerrado')
    ])

    @api.depends('line_ids.product_id')
    def _compute_items_ids(self):
        for record in self:
            if record.line_ids:
                items = record.line_ids.mapped('product_id.categ_id.parent_id')
                items = items.filtered(lambda c: c and c.id).ids
                record.items_ids = [(6, 0, items)]
            else:
                record.items_ids = [(5, 0, 0)]

    
    @api.depends('line_ids')
    def _compute_bultos_count(self):
        for record in self:
            if record.line_ids:
                record.bultos_count = sum(record.line_ids.mapped('bultos'))

    @api.depends('line_ids')
    def _compute_lines_count(self):
        for record in self:
            if record.line_ids:
                record.lines_count = len(record.line_ids)


    def action_confirm(self):
        for record in self:
            
            transfer_vals = {
                'partner_id': record.partner_id.id,
                'operation_type': 'internal',
                'preselection_id': record.id,                
            }

            transfer_id = self.env['wms.transfer'].create(transfer_vals)

            transfer_lines_vals_list = []
            for line in record.line_ids:
                transfer_line = {
                    'transfer_id': transfer_id.id,
                    'product_id': line.product_id.id,
                    'state': 'pending',
                    'invoice_state': 'no',
                    'sale_line_id': line.id,
                    'uxb': line.product_packaging_id.qty or False,
                    'qty_demand': line.quantity,
                }
                transfer_lines_vals_list.append(transfer_line)
            
            self.env['wms.transfer.line'].create(transfer_lines_vals_list)

            record.transfer_id = transfer_id.id
            record.state = 'confirmed'



class WMSPreselectionLine(models.Model):
    _name = 'wms.preselection.line'

    preselection_id = fields.Many2one(string="Preselección", comodel_name="wms.preselection")
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    bultos = fields.Float(string="Bultos", compute="_compute_bultos", store=True)
    uxb = fields.Integer(string="UxB")
    quantity = fields.Integer(string="Demanda")
    quantity_prepared = fields.Integer(string="Preparado")
    quantity_delivered = fields.Integer(string="Entregado")
    quantity_invoiced = fields.Integer(string="Facturado")


    @api.depends('quantity')
    def _compute_bultos(self):
        for record in self:
            if record.product_id and record.quantity > 0:
                record.bultos = record.quantity / record.uxb


    @api.onchange('product_id')
    def _onchange_uxb(self):
        for record in self:
            if record.product_id:
                record.uxb = record.product_id.packaging_ids[0].qty or 1

    
    @api.onchange('quantity')
    def _onchange_quantity(self):
        for record in self:
            if record.quantity == 0:
                raise UserWarning('La demanda debe ser mayor a 0')