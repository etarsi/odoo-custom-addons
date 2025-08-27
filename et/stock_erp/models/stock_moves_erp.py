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

class StockMovesERP(models.Model):
    _name = 'stock.moves.erp'

    
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


    def get_uxb(self):
        for record in self:
            if record.product_id.packaging_ids:
                record.uxb = record.product_id.packaging_ids[0].qty


    def set_to_zero(self):
        self.fisico_unidades = 0