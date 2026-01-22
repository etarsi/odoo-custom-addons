from odoo import models, fields, api


class WMSTransfer(models.Model):
    _name = 'wms.transfer'

    name = fields.Char()
    partner_id = fields.Many2one(string="Cliente", comodel_name="res.partner")
    partner_address_id = fields.Many2one(string="Dirección de Entrega", comodel_name="res.partner")
    operation_type = fields.Selection(string="Tipo de Operación", selection=[
        ('incoming', 'Ingreso'),
        ('outgoing', 'Entrega')
    ])
    sale_type = fields.Char(string="TIPO")
    sale_id = fields.Many2one(string="Pedido de Venta", comodel_name="sale.order")
    purchase_id = fields.Many2one(string="Pedido de Compra", comodel_name="purchase.order")
    # invoice_ids = fields.One2many(string="Facturas", comodel_name="account.move", inverse_name="transfer_id")
    line_ids = fields.One2many(string="Líneas de  Transferencia", comodel_name="wms.transfer.line", inverse_name="transfer_id")
    # task_ids = fields.One2many(string="Tareas", comodel_name="wms.task", inverse_name="transfer_id")



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
        ('partial'), ('Parcial'),
        ('total', 'Facturado')
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

