from odoo import models, fields, api, _
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError, AccessError
import logging
import math
import requests
from itertools import groupby
from datetime import timedelta

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
    state = fields.Selection(string="Estado", default='draft', selection=[('draft','Borrador'), ('pending', 'Pendiente'), ('inprogress', 'En Proceso'), ('confirmed', 'Confirmado'), ('done', 'Hecho')])
    move_lines = fields.One2many('return.move.line', 'return_move', string="Devoluciones Sanas")
    return_move_lines = fields.One2many('return.move.line', 'return_move', string="Devoluciones rotas")
    price_total = fields.Float(string="Total", compute="_compute_price_total")
    company_id = fields.Many2one('res.company', string="Compañía")
    wms_code = fields.Char("Código WMS")

    
    def _compute_price_total(self):
        for record in self:
            record.price_total = sum(record.move_lines.mapped('price_subtotal'))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for record in self:
            if record.partner_id:
                journals = self.env['account.journal'].search([
                    ('code', '=', '00010')
                ])
                domain = [
                    ('partner_id', '=', record.partner_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted')
                ]
                if journals:
                    domain.append(('journal_id', 'in', journals.ids))
                else:
                    domain.append(('journal_id', '=', 0))
                    
                last_invoice = self.env['account.move'].search(domain, order='date desc', limit=1)

                if last_invoice:
                    record.invoice_id = last_invoice


    def action_send_return(self):        
        
        headers = {}
        json = {
            "Numero": "R1",
            "Factura": "",
            "Fecha": "2025-08-07 16:12:00",
            "CodigoProveedor": "WALDEN TOYS",
            "Observacion": "Prueba de Odoo",
            "DocumentoRecepcionTipo": "remito",
            "RecepcionTipo": "devolucion",
            "DocumentoRecepcionDetalleRequest": [
            ]
            }
        
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        response = requests.post('http://api.patagoniawms.com/v1/DocumentoRecepcion', headers=headers, json=json)

        if response.status_code == 200:
            self.state == 'inprogress'
            self.wms_code = 'R1'
        else:
            raise UserError(f'Error code: {response.status_code} - Error Msg: {response.text}')



class ReturnMoveLine(models.Model):
    _name = 'return.move.line'

    name = fields.Char(string="Nombre", required=True, default="Remito de prueba")
    return_move = fields.Many2one('return.move', string="Devolución")
    product_id = fields.Many2one('product.product', string="Producto")
    quantity = fields.Integer(string="Cantidad")
    uxb = fields.Integer(string="UxB")
    bultos = fields.Float(string="Bultos")
    price_unit = fields.Float(string="Precio Unitario")
    discount = fields.Float(string="Descuento")
    price_subtotal = fields.Float(string="Precio Subtotal")
    is_broken = fields.Boolean("¿Roto?")
    wib = fields.Char(string="¿Qué está roto?")

    def get_last_price(self):

        last_invoice_line = self.env['account.move.line'].search([
            ('product_id', '=', self.id),
            ('parent_state', '=', 'posted'),
        ], order='date dsc', limit=1)

        if last_invoice_line:
            self.price_unit = last_invoice_line.price_unit