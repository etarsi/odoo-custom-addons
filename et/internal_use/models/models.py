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

class InternalUse(models.Model):
    _name = 'internal.use'
    _description = 'Uso Interno'

    name = fields.Char()
    date = fields.Datetime(string='Fecha solicitud')
    requester = fields.Char(string='Solicitante')
    move_type = fields.Selection(selection=[('ingoing', 'Ingreso'), ('outgoing', 'Entrega')])
    internal_use_items = fields.One2many('internal.use.items', 'internal_use')



class InternalUseItems(models.Model):
    _name = 'internal.use.items'

    internal_use = fields.Many2one('internal.use')
    product_id = fields.Many2one('product.product')
    quantity = fields.Integer(string='Cantidad')
    last_requested_date = fields.Datetime()
    last_request_by = fields.Char()