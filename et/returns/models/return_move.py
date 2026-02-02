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
_logger = logging.getLogger(__name__)

class ReturnMove(models.Model):
    _name = 'return.move'

    name = fields.Char(string="Nombre", required=True, default="/")
    partner_id = fields.Many2one('res.partner', string="Cliente")
    sale_id = fields.Many2one('sale.order', string="Pedido de Venta")
    cause = fields.Selection(string="Motivo", default=False, selection=[
        ('error', 'Producto Erróneo'),
        ('broken','Producto Roto'),
        ('no', 'No lo quiere'),
        ('expensive', 'Muy caro'),
        ('bad', 'No lo pudo vender')])
    info = fields.Text(string="Información adicional")
    date = fields.Date(string="Fecha de Recepción", default=fields.Date.today)
    state = fields.Selection(string="Estado", default='draft', selection=[
        ('draft','Borrador'), 
        ('pending', 'Pendiente'), 
        ('inprogress', 'En Proceso'), 
        ('confirmed', 'Confirmado'), 
        ('done', 'Hecho')
    ])
    move_lines = fields.One2many('return.move.line', 'return_move', string="Devoluciones Sanas")
    price_total = fields.Float(string="Total", compute="_compute_price_total")
    company_id = fields.Many2one('res.company', string="Compañía")
    wms_code = fields.Char("Código WMS")


    credit_notes = fields.One2many(string="Notas de Crédito", comodel_name="account.move", inverse_name="return_id")
    credit_count = fields.Integer(string="Notas de Crédito", compute="_compute_credit_count")


    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'

    ### COMPUTED ###

    @api.depends('move_lines.price_subtotal')
    def _compute_price_total(self):
        for record in self:
            if record.move_lines:
                record.price_total = sum(record.move_lines.mapped('price_subtotal'))


    @api.depends('credit_notes')
    def _compute_credit_count(self):
        for record in self:
            record.credit_count = len(record.credit_notes)

    ### ONCHANGE ###

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for record in self:
            if record.partner_id:
                journals = self.env['account.journal'].search([
                    ('code', 'in', ['00010', '00009'])
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
        for record in self:
            
            next_number = self.env['ir.sequence'].sudo().next_by_code('DEV')
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            provider = record.get_current_provider(record.partner_id)

            payload = {
                "Numero": f'R{next_number}',
                "Factura": "",
                "Fecha": str(record.date),
                "CodigoProveedor": provider['code'],
                "Proveedor": provider['name'],
                "Observacion": "Prueba de Odoo",
                "DocumentoRecepcionTipo": "remito",
                "RecepcionTipo": "devolucion",
                "DocumentoRecepcionDetalleRequest": [
                ]
            }          
            
            
            headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
            response = requests.post('http://api.patagoniawms.com/v1/DocumentoRecepcion', headers=headers, json=payload)

            if response.status_code == 200:
                record.state = 'inprogress'
                record.wms_code = f'R{next_number}'
                record.name = record.get_document_name(next_number)
            else:
                raise UserError(f'Error code: {response.status_code} - Error Msg: {response.text}')


    def get_current_provider(self, partner_id):
        current_provider = {
            'code': "",
            'name': "",
        }
        
        providers = self.get_providers()

        for p in providers:
                if p['Activo']:
                    if p['Descripcion'] == partner_id.name:
                        current_provider['code'] = p['Codigo']
                        current_provider['name'] = p['Descripcion']
                        return current_provider

        if not current_provider['code']:        
            current_provider = self.create_provider(partner_id)
            return current_provider
            

    def get_providers(self):
        
        headers = {}
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        
        response = requests.get('http://api.patagoniawms.com/v1/Proveedor', headers=headers)

        if response.status_code == 200:
            data = response.json()
            return data        
        else:
            raise UserError(f'No se pudo obtener los proveedores de Digip. STATUS_CODE: {response.status_code}')


    def create_provider(self, provider):
        current_provider = {}
        headers = {}
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        payload = {
                "Codigo": str(provider.id),
                "Descripcion": provider.name,
                "RequiereControlCiego": True,
                "Activo": True,
                }
        response = requests.post('http://api.patagoniawms.com/v1/Proveedor', headers=headers, json=payload)

        if response.status_code == 204:
            current_provider['code'] = provider.id
            current_provider['name'] = provider.name

            return current_provider
        else:
            raise UserError(f'No se pudo crear el proveedor en Digip. STATUS_CODE: {response.status_code}')
        


    def get_document_name(self, next_number):
        
        name = f'DEV-{next_number}'

        return name


    # def receive_from_digip(self):
    #     self.get_random_products()


    # def get_random_products(self):
    #     return_move_lines = self.env['return.move.line']
    #     for record in self:
    #         vals = {
                
    #         }



class ReturnMoveLine(models.Model):
    _name = 'return.move.line'

    name = fields.Char(string="Nombre", required=True, default="Remito de prueba")
    return_move = fields.Many2one('return.move', string="Devolución")
    product_id = fields.Many2one('product.product', string="Producto")
    quantity_healthy = fields.Integer(string="Cantidad Sana")
    quantity_broken = fields.Integer(string="Cantidad Rota")
    quantity_total = fields.Integer(string="Total", compute="_compute_quantity_total")
    uxb = fields.Integer(string="UxB")
    bultos = fields.Float(string="Bultos", compute="_compute_bultos")
    price_unit = fields.Float(string="Precio Unitario")
    discount = fields.Float(string="Descuento")
    price_subtotal = fields.Float(string="Precio Subtotal", compute="_compute_subtotal")
    state = fields.Selection(string='State', selection=[('draft','Borrador'), ('confirmed','Confirmado'), ('done', 'Hecho')])
    company_id = fields.Many2one(string="Compañía", comodel_name="res.company")

    invoice_id = fields.Many2one(string="Factura Asociada", comodel_name="account.move")
    invoice_line_id = fields.Many2one(string="Línea de Factura Asociada", comodel_name="account.move.line")


    @api.model
    def create(self, vals):
        res = super().create(vals)

        for r in res:
            r.update_prices()

        return res


    @api.onchange('product_id')
    def _onchang_product_uxb(self):
        for record in self:
            if record.product_id:
                record.uxb = record.get_product_uxb(record.product_id)


    @api.depends('quantity_healthy', 'quantity_broken')
    def _compute_quantity_total(self):
        for record in self:
            record.quantity_total = record.quantity_healthy + record.quantity_broken

    
    @api.depends('price_unit', 'quantity_total', 'discount')
    def _compute_subtotal(self):
        for record in self:
            record.price_subtotal = record.price_unit * record.quantity_total * record.discount / 100
    

    def update_prices(self):
        for record in self:
            record.invoice_line_id = record.get_last_invoice_line()

            if record.invoice_line_id:
                record.invoice_id = record.invoice_line_id.move_id.id
                record.price_unit = record.invoice_line_id.price_unit
                record.discount = record.invoice_line_id.discount                
                record.company_id = record.invoice_line_id.company_id.id


                # CONDICIONAL A REVISAR
                # if record.invoice_line_id.company_id.id == 1:
                #     record.price_unit = record.invoice_line_id.price_unit / 1.21
                #     record.company_id = 2
                #     record.discount = record.invoice_line_id.discount
                # else:
                #     record.price_unit = record.invoice_line_id.price_unit
                #     record.company_id = record.invoice_line_id.company_id.id
                #     record.discount = record.invoice_line_id.discount


    def get_last_invoice_line(self):
        for record in self:
            last_invoice_line = self.env['account.move.line'].search([
                ('partner_id', '=', record.return_move.partner_id.id),
                ('product_id', '=', record.product_id.id),
                ('parent_state', '=', 'posted'),
            ], order='date desc', limit=1)

            if last_invoice_line:
                return last_invoice_line
            

    def get_product_uxb(self, product_id):
        if product_id.packaging_ids:
            return product_id.packaging_ids[0].qty
        

    @api.depends('quantity_total')
    def _compute_bultos(self):
        for record in self:
            if record.uxb != 0:
                record.bultos = record.quantity_total / record.uxb
            else:
                record.bultos = 0
