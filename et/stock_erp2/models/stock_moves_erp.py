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

class StockMovesERP2(models.Model):
    _name = 'stock.moves.erp2'

    
    name = fields.Char()
    stock_erp = fields.Many2one('stock.erp2')
    sale_id = fields.Many2one('sale.order')
    picking_id = fields.Many2one('stock.picking')
    product_id = fields.Many2one('product.template')
    quantity = fields.Integer()
    bultos = fields.Float()
    uxb = fields.Integer()

