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

class ProductTemplateInherit(models.Model):
    _inherit = "product.template"

    company_ids = fields.Many2many('res.company', string='Compañias Permitidas', help='Compañias que pueden usar este producto.')
    