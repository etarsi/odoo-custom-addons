from odoo import tools, models, fields, api, _
import html2text
from odoo.exceptions import UserError, ValidationError
import logging
import requests
from requests.structures import CaseInsensitiveDict
import re
import math
from collections import defaultdict
null=None

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    codigo_wms = fields.Char(string="Código WMS", related='picking_id.condigo_wms', store=True)
    