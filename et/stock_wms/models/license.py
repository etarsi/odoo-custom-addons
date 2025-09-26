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


class License(models.Model):
    _name = 'license'
    _description = 'Licencia'

    name = fields.Char()
    containers = fields.One2many('license.container', 'license', string="Contenedores")
    dispatch_number = fields.Char()



class LicenseContainer(models.Model):
    _name = 'license.container'


    name = fields.Char()
    license = fields.Many2one('license')