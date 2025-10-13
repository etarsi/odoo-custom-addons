from odoo import models, fields, api, _
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
import logging
import math
import requests
from itertools import groupby
from datetime import timedelta

class StockMoveInherit(models.Model):
    _inherit = "stock.move"

    product_available_percent = fields.Float(string='Porc Disponible', compute='_calculate_bultos', store=True, group_operator='avg')
    product_packaging_qty = fields.Float(string='Bultos', compute='_calculate_bultos', store=True)
    product_available_pkg_qty = fields.Float(string='Bultos Disponibles', compute='_calculate_bultos', store=True)

    availability = fields.Char(string="Disponible")
    license = fields.Char(string="Licencia", related='picking_id.carrier_tracking_ref', store=True)

    @api.depends('quantity_done', 'product_uom_qty')
    def _calculate_bultos(self):
        for record in self:
            if record.product_uom_qty > 0:
                record.product_available_percent = (record.quantity_done * 100) / record.product_uom_qty



    @