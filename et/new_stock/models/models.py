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

    product_id = fields.Many2one('product.product', string='Producto')
    