from odoo import models, fields, api


class WMSTransfer(models.Model):
    _name = 'wms.transfer'

    name = fields.Char()
    partner_id = fields.Many2one(string="Cliente", comodel_name="res.partner")
    partner_address_id = fields.Many2one(string="Dirección de Entrega", comodel_name="res.partner")
    operation_type = fields.Selection(string="Tipo de Operación", selection=[
        ('incoming', 'Ingreso'),
        ('return', 'Devolución'),
        ('internal', 'Interno'),
        ('outgoing', 'Entrega'),
    ])
    state_general = fields.Char(string="Estado")
    state_incoming = fields.Selection(string="Estado", selection=[
        ('no', 'No aplica')
        ('pending', 'Pendiente'),
        ('preparation', 'En Preparación'),
        ('')
    ])
    sale_type = fields.Char(string="TIPO")
    sale_id = fields.Many2one(string="Pedido de Venta", comodel_name="sale.order")
    purchase_id = fields.Many2one(string="Pedido de Compra", comodel_name="purchase.order")
    # invoice_ids = fields.One2many(string="Facturas", comodel_name="account.move", inverse_name="transfer_id")
    line_ids = fields.One2many(string="Líneas de  Transferencia", comodel_name="wms.transfer.line", inverse_name="transfer_id")
    task_ids = fields.One2many(string="Tareas", comodel_name="wms.task", inverse_name="transfer_id")
    task_count = fields.Integer(string="Tareas", compute="_compute_task_count", store=True)
    lines_count = fields.Integer(string="Líneas de Transf")
    origin = fields.Char(string="Documento")
    

    partner_tag = fields.Many2many()

    time_elapsed = fields.Date(string="Días de Atraso")
    total_bultos = fields.Float(string="Bultos")
    total_bultos_prepared = fields.Float(string="Bultos Preparados")
    total_available_percentage = fields.Float(string="Porcentaje Disponible")


    @api.model
    def create(self, vals):
        if vals.get('name', 'New') in (False, 'New', '/'):
            vals['name'] = self.env['ir.sequence'].next_by_code('wms.transfer') or 'New'

        sale_id = vals.get('sale_id')
        if sale_id and 'origin' in self._fields and not vals.get('origin'):
            sale = self.env['sale.order'].browse(sale_id)
            if sale.exists():
                vals['origin'] = sale.name

        purchase_id = vals.get('purchase_id')
        if purchase_id and 'origin' in self._fields and not vals.get('origin'):
            purchase = self.env['purchase.order'].browse(purchase_id)
            if purchase.exists():
                vals['origin'] = purchase.name


        return super().create(vals)


    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    @api.depends('line_ids')
    def _compute_lines_count(self):
        for rec in self:
            rec.lines_count = len(rec.line_ids)


    @api.onchange('line_ids.bultos')
    def _onchange_bultos(self):
        for record in self:
            if record.line_ids:
                record.total_bultos = 0 # ESTABA VACIO -> TITO  



class WMSTransferLine(models.Model):
    _name = 'wms.transfer.line'

    name = fields.Char()
    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")
    state = fields.Selection(string="Estado", selection=[
        ('pending', 'Pendiente'),
        ('preparation', 'En Preparación'),
        ('done', 'Hecho'),
    ])
    invoice_state = fields.Selection(string="Estado de Facturación", selection=[
        ('no', 'No Facturado'),
        ('partial', 'Parcial'),
        ('total', 'Facturado'),
    ])
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    sale_line_id = fields.Many2one(string="Línea del Pedido de Venta", comodel_name="sale.order.line")
    lot_name = fields.Char(string="Lote")
    uxb = fields.Integer(string="UxB")
    availability = fields.Char(string="Disponibilidad")
    qty_demand = fields.Integer(string="Demanda")
    qty_done = fields.Integer(string="Hecho")
    qty_invoiced = fields.Integer(string="Facturado")
    available_percent = fields.Char(string="Disponible %")
