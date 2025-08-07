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


class StockWMS(models.Model):
    _name = 'stock.wms'
    _description = 'Stock WMS'

    name = fields.Char()

    product_id = fields.Many2one('product.template', string='Producto', required=True)
    product_name = fields.Char(string='Producto')
    uxb = fields.Char('UxB')

    fisico_unidades = fields.Integer('Físico Unidades')
    enelagua_unidades = fields.Integer('En el Agua Unidades')
    total_unidades = fields.Integer('Total Unidades')
    reservado_unidades = fields.Integer('Reservado Unidades')
    disponible_unidades = fields.Float('Disponible Unidades', digits=(99,0))
    entregable_unidades = fields.Integer('Entregable Unidades')
    comprado_unidades = fields.Integer('Comprado Unidades')
    entrante_unidades = fields.Integer('Entrante Unidades')

    fisico_bultos = fields.Float('Físico Bultos')
    enelagua_bultos = fields.Float('En el Agua Bultos')    
    total_bultos = fields.Float('Total Bultos')
    reservado_bultos = fields.Float('Reservado Bultos')
    disponible_bultos = fields.Float('Disponible Bultos')    
    entregable_bultos = fields.Float('Entregable Bultos')
    comprado_bultos = fields.Float('Comprado Bultos')
    entrante_bultos = fields.Float('Entrante Bultos')

    entrante_fecha = fields.Date('ETA')
    entrante_licencia = fields.Char('Licencia')

    ultima_actualizacion = fields.Datetime('Última actualización')

    # teórico

    def create_initial_products(self):

        stock_digip = self.get_digip_stock()
        stock_wms = self.env['stock.wms']
        vals_list = []

        for record in stock_digip:
            product_id = self.env['product.template'].search([('default_code', '=', record['codigo'])], limit=1)
            if product_id:
                vals = {
                    'product_id': product_id.id,
                    'fisico_unidades': record['stock']['disponible']
                }
                vals_list.append(vals)
        stock_wms.create(vals_list)

    

    def get_digip_stock(self):
        headers = {}
        
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms-v2.url')
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        response = requests.get(f'{url}/v2/Stock/Tipo', headers=headers)

        if response.status_code == 200:
            products = response.json()
            if products:
                return products

        elif response.status_code == 400:
            raise UserError('ERROR: 400 BAD REQUEST. Avise a su administrador de sistema.')
        elif response.status_code == 404:
            raise UserError('ERROR: 404 NOT FOUND. Avise a su administrador de sistema.')
        elif response.status_code == 500:
            raise UserError('ERROR: 500 INTERNAL SERVER ERROR. Avise a su administrador de sistema. Probablemente alguno de los productos no se encuentra creado en Digip.')        

    def get_comprado(self):
        global_purchases = self.env['purchase.order'].search([('china_purchase','=', True)])

        return global_purchases
    
    def get_enelagua(self):
        # product_uom
        # product_qty
        # qty_received
        purchased = self.get_comprado()
        containers = self.env['stock.picking'].search([('partner_id','=', 16571), ('picking_type_code','!=','outgoing')])

        
    def get_fisico_bultos(self):
        for record in self:
            if record.fisico_unidades > 0:
                record.fisico_bultos = record.fisico_unidades / float(record.uxb)


    
    # def get_comprometido(self)

    # def get_disponible(self):

    # def get_reservado(self):

    # def get_entrante(self):

    # def get_bultos(self, uxb):