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


class ProductMove(models.Model):
    _name = 'product.move'

    date = fields.Datetime(string="Fecha")
    type = fields.Char(string="Tipo")

    product_id = fields.Many2one('product.product', string="Producto")
    product_code = fields.Char(string="Código")
    product_name = fields.Char(string="Nombre")
    categ_id = fields.Char(string="Categoría de Producto")
    
    quantity = fields.Integer(string="Cantidad")
    uxb = fields.Char(string="UxB")
    lot = fields.Char(string="Lote")
    cmv = fields.Float(string="CMV")
    
    partner_id = fields.Many2one('res.partner',string="Cliente")
    company_id = fields.Char(string="Compañía")
    picking_id = fields.Many2one('stock.picking', string="Transferencia")

    wms_code = fields.Char(string="Código WMS")
    license = fields.Char(string="Licencia")
    container = fields.Char(string="Contenedor")
    dispatch = fields.Char(string="Despacho")