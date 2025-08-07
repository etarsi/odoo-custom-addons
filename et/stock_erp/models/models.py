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

class StockERP(models.Model):
    _name = 'stock.erp'

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


    def get_stock_wms(self):
        for record in self:
            stock_wms = self.env['stock.wms'].search([('product_id', '=', record.product_id.id)], limit=1)

            if stock_wms:
                record.fisico_unidades = stock_wms.fisico_unidades

    def create_initial_products(self):
        stock_wms = self.env['stock.wms']
        stock_erp = self.env['stock.erp']
        stock_wms_records = stock_wms.search([])
        vals_list = []

        for record in stock_wms_records:
            vals = {
                'product_id': record.product_id.id,
                'uxb': record.uxb,
                'fisico_unidades': record.fisico_unidades,
            }
            vals_list.append(vals)
        stock_erp.create(vals_list)

    