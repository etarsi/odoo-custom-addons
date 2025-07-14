from odoo import models, fields

class ReturnMove(models.Model):
    _name = 'return.move'

    name = fields.Char(string="Nombre", required=True, default="/")
    partner_id = fields.Many2one('res.partner', string="Cliente")
    sale_id = fields.Many2one('sale.order', string="Pedido de Venta")
    invoice_id = fields.Many2one('account.move', string="Factura")
    cause = fields.Selection(string="Motivo", default=False, selection=[
        ('error', 'Producto Erróneo'),
        ('broken','Producto Roto'),
        ('no', 'No lo quiere'),
        ('expensive', 'Muy caro'),
        ('bad', 'No lo pudo vender')])
    info = fields.Text(string="Información adicional")
    date = fields.Date(string="Fecha de Recepción", default=fields.Date.today)
    state = fields.Selection(string="Estado", default='draft', selection=[('draft','Borrador'), ('inprogress', 'En Proceso'), ('confirmed', 'Confirmado'), ('done', 'Hecho')])
    move_lines = fields.One2many('return.move.line', 'return_move', string="Devoluciones Sanas")
    return_move_lines = fields.One2many('return.move.line', 'return_move', string="Devoluciones rotas")
    price_total = fields.Float(string="Total", compute="_compute_price_total")
    company_id = fields.Many2one('res.company', string="Compañía")

    
    def _compute_price_total(self):
        for record in self:
            record.price_total = sum(record.move_lines.mapped('price_subtotal'))

class ReturnMoveLine(models.Model):
    _name = 'return.move.line'

    name = fields.Char(string="Nombre", required=True, default="Remito de prueba")
    return_move = fields.Many2one('return.move', string="Devolución")
    product_id = fields.Many2one('product.product', string="Producto")
    quantity = fields.Integer(string="Cantidad")
    uxb = fields.Integer(string="UxB")
    bultos = fields.Float(string="Bultos")
    price_unit = fields.Float(string="Precio Unitario")
    price_subtotal = fields.Float(string="Precio Subtotal")
    is_broken = fields.Boolean("¿Roto?")
    wib = fields.Char(string="¿Qué está roto?")