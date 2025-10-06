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


class Container(models.Model):
    _name = 'container'
    _description = 'Contenedor'

    name = fields.Char()
    china_purchase = fields.Many2one('china.purchase', string="Compra China")
    lines = fields.One2many('container.line', 'container', string="Productos")
    license = fields.Char()
    dispatch_number = fields.Char()
    eta = fields.Date()
    state = fields.Selection(selection=[('draft', 'Borrador'), ('sent', 'Enviado'), ('received', 'Recibido'), ('confirmed', 'Confirmado')], default='draft')
    wms_code = fields.Char()
    product_ids = fields.Many2many('product.product', compute='_compute_product_ids', string='Productos')

    @api.depends('lines.product_id')
    def _compute_product_ids(self):
        for record in self:
            record.product_ids = record.lines.mapped('product_id')
    
    def enviar(self):        
        for record in self:
            
            next_number = self.env['ir.sequence'].sudo().next_by_code('DIGIP_C')
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            product_list = record.get_product_list()

            payload = {
                "Numero": f'{next_number}',
                "Factura": "",
                "Fecha": str(fields.Date.context_today(self)),
                "CodigoProveedor": "16571",
                "Proveedor": "ZHEJIANG YUFUN ELEC TECH CO., LTD",
                "Observacion": record.name,
                "DocumentoRecepcionTipo": "remito",
                "RecepcionTipo": "abastecimiento",
                "DocumentoRecepcionDetalleRequest": product_list
            }          
            
            
            headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
            response = requests.post('http://api.patagoniawms.com/v1/DocumentoRecepcion', headers=headers, json=payload)

            if response.status_code == 200:
                record.wms_code = f'{next_number}'
                record.state = 'sent'
            else:
                raise UserError(f'Error code: {response.status_code} - Error Msg: {response.text}')


    def anular_envio(self):
        for record in self:
            record.state = 'draft'
            record.wms_code = ''




    def recibir(self):
        for record in self:

            headers = {
                "Content-Type": "application/json",
            }

            
            params = {
                'DocumentoNumero': record.wms_code,
            }

            headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
            response = requests.get("http://api.patagoniawms.com/v1/ControlCiego", headers=headers, json=params)

            if response.status_code == 200:
                # record.state = 'received'

                data = response.json()
                if data['Estado'] == 'Verificado' and data['Modo'] == 'Completo':
                    if data['ControlCiegoDetalle']:
                        for element in data['ControlCiegoDetalle']:
                            raise UserError(f"Producto {element['Articulo']} - Cantidad {element['Unidades']}")

            else:
                raise UserError(f'Error code: {response.status_code} - Error Msg: {response.text}')
            
    
    def confirmar(self):
        for record in self:
            if record.state == 'confirmed':
                raise UserError('Contenedor ya confirmado')
            
            for line in record.lines: 
                if not record.china_purchase:
                    raise UserError('No se puede confirmar un contenedor que no tiene asociada una orden de compra china.')
                

                china_purchase_line = self.env['china.purchase.line'].search([('product_id', '=', line.product_id.id)], limit=1)

                if china_purchase_line:
                    china_purchase_line.quantity_received += line.quantity_picked

                stock_erp = self.env['stock.erp'].search([('product_id', '=', line.product_id.id)], limit=1)

                if stock_erp:

                    if line.quantity_picked >= stock_erp.enelagua_unidades:
                        stock_erp.enelagua_unidades = 0
                    else:
                        stock_erp.enelagua_unidades -= line.quantity_picked

                    stock_erp.fisico_unidades += line.quantity_picked
                    stock_erp.entregable_unidades += line.quantity_picked
                else:
                    raise UserError(f'No se encuentra el producto [{line.product_id.default_code}]{line.product_id.name} en el Stock')
                
            record.state = 'confirmed'


    @api.onchange('eta')
    def _onchange_eta(self):
        for record in self:
            if record.eta:
                if record.lines:
                    for line in record.lines:
                        stock_erp = self.env['stock.erp'].search([('product_id', '=', line.product_id.id)], limit=1)

                        if stock_erp:
                            eta = stock_erp.entrante_fecha

                            if eta:
                                if eta <= record.eta:
                                    continue
                                else:
                                    eta = record.eta
                                    stock_erp.entrante_licencia = record.license
                            else:
                                eta = record.eta
                                stock_erp.entrante_licencia = record.license
                        else:
                            raise UserError(f'No se encuentra el producto [{line.product_id.default_code}]{line.product_id.name} en el Stock')


    def get_product_list(self):
        for record in self:
            product_list = []
            if record.lines:
                for line in record.lines:
                    product_info = {}
                    product_info['CodigoArticulo'] = line.product_id.default_code
                    product_info['Unidades'] = line.quantity_send

                    product_list.append(product_info)

            return product_list




class ContainerLine(models.Model):
    _name = 'container.line'


    name = fields.Char()
    container = fields.Many2one('container', string='Contenedor')
    product_id = fields.Many2one('product.product', string='Producto')
    product_code = fields.Char(string="Código", compute="_compute_product_code", store=True)
    product_name = fields.Char(string="Nombre", compute="_compute_product_name", store=True)
    quantity_send = fields.Integer()
    quantity_picked = fields.Integer()
    uxb = fields.Integer(string="Uxb", compute="_compute_uxb", store=True)
    bultos = fields.Float(string="Bultos", compute="_compute_bultos", store=True)


    item_code = fields.Float()
    fake_code = fields.Float()
    bar_code = fields.Float()
    dun14_master = fields.Float()
    dun14_inner = fields.Float()
    dun14_display = fields.Float()


    @api.depends('product_id')
    def _compute_product_code(self):
        for record in self:
            if record.product_id:
                record.product_code = record.product_id.default_code
            else:
                record.product_code = ''


    @api.depends('product_id')
    def _compute_product_name(self):
        for record in self:
            if record.product_id:
                record.product_name= record.product_id.name
            else:
                record.product_name = ''


    @api.depends('product_id')
    def _compute_uxb(self):
        for record in self:
            if record.product_id:
                if record.product_id.packaging_ids:
                    record.uxb = record.product_id.packaging_ids[0].qty
            else:
                record.uxb = None
    

    @api.depends('quantity_send', 'quantity_picked')
    def _compute_bultos(self):
        for record in self:
            if record.uxb:
                if record.quantity_picked > 0:
                    record.bultos = record.quantity_picked / record.uxb
                else:
                    record.bultos = record.quantity_send / record.uxb
            else:
                record.bultos = 0
