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


class NewStock(models.Model):
    _name = 'new.stock'
    _description = 'Stock Detallado'

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
    comprado_bultos = fields.Float
    entrante_bultos = fields.Float('Entrante Bultos')

    entrante_fecha = fields.Date('ETA')
    entrante_licencia = fields.Char('Licencia')

    ultima_actualizacion = fields.Datetime('Última actualización')

    # teórico

    def create_initial_products(self):
        current_products = self.env['product.template'].search([
            ('detailed_type', '=', 'product'),
            ('categ_id.parent_id', 'not in', [1, 756, 763]),
            ('default_code', 'not like', '9%')
        ])

        new_stock = self.env['new.stock']
        vals_list = []
        for product in current_products:
            vals_list.append({
                'product_id': product.id if product.id else False,
                'product_name': product.name if product.name else False,
                # 'default_code': product.default_code,
                'uxb': product.uom_po_id.name if product.uom_po_id else False,
            })
        if vals_list:
            new_stock.create(vals_list)

    def update_product_list(self):
        existing_product_ids = set(
            self.env['new.stock'].search([]).mapped('product_id').ids
        )

        current_products = self.env['product.template'].search([
            ('detailed_type', '=', 'product'),
            ('categ_id.parent_id', 'not in', [1, 756, 763]),
            ('id', 'not in', list(existing_product_ids))
        ], fields=['name', 'default_code', 'uom_po_id'])

        vals_list = []
        for product in current_products:
            vals_list.append({
                'product_id': product.id,                
                'product_name': product.name,
                'default_code': product.default_code,
                'uom_name': product.uom_po_id.name if product.uom_po_id else False,
            })
        if vals_list:
            self.env['new.stock'].create(vals_list)


    def update_products_info(self):
        fisico_unidades = self.get_fisico()



    def get_fisico(self):
        new_stock = self.env['new.stock'].search([])
        product_ids = self.env['new.stock'].search([('product_id', '!=', False)]).mapped('product_id')
        product_codes = set(product_ids.mapped('default_code'))
        digip_stock = self._get_digip_stock_en_lotes(product_codes)
        
        stock_by_code = {
            p['codigo']: p['stock']['disponible']
            for p in digip_stock
        }

        for s in new_stock:
            code = s.product_id.default_code
            disponible = stock_by_code.get(code, 0)

            s.fisico_unidades = disponible
            s.get_fisico_bultos()
            s.ultima_actualizacion = fields.Datetime.now()

    def _get_digip_stock_en_lotes(self, product_codes, max_por_lote=387):
        product_codes = list(product_codes)
        total_stock = []

        for i in range(0, len(product_codes), max_por_lote):
            lote = product_codes[i:i + max_por_lote]
            _logger.info(f"[STOCK] Llamando API para lote {i // max_por_lote + 1} con {len(lote)} códigos")
            lote_stock = self.get_digip_stock(lote)
            if lote_stock:
                total_stock.extend(lote_stock)

        return total_stock

    def get_digip_stock(self, lote):
        headers = {}
        params = {}
        
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms-v2.url')
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        params = {
            'ArticuloCodigo': lote
        }
        response = requests.get(f'{url}/v2/Stock/Tipo', headers=headers, params=params)

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