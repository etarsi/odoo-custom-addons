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


class NewStock(models.Model):
    _name = 'new.stock'
    _description = 'Stock Detallado'

    name = fields.Char()

    product_id = fields.Many2one('product.template', string='Producto')
    product_name = fields.Char(string='Producto')
    uxb = fields.Char('UxB')

    fisico_unidades = fields.Integer('Físico Unidades')
    comprometido_unidades = fields.Integer('Comprometido Unidades')
    disponible_unidades = fields.Integer('Disponible Unidades')
    reservado_unidades = fields.Integer('Reservado Unidades')
    entrante_unidades = fields.Integer('Entrante Unidades')

    fisico_bultos = fields.Float('Físico Bultos')    
    comprometido_bultos = fields.Float('Comprometido Bultos')    
    disponible_bultos = fields.Float('Disponible Bultos')    
    reservado_bultos = fields.Float('Reservado Bultos')
    entrante_bultos = fields.Float('Entrante Bultos')

    entrante_fecha = fields.Date('ETA')
    entrante_licencia = fields.Char('Licencia')

    ultima_actualizacion = fields.Date('Última actualización')


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
                'product_name': product.name,
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


    # def update_products_info(self):

    # def get_fisico(self)

    # def get_comprometido(self)

    # def get_disponible(self):

    # def get_reservado(self):

    # def get_entrante(self):

    # def get_bultos(self, uxb):