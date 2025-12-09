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

class StockProductionLotInherit(models.Model):
    _inherit = "stock.production.lot"

    @api.model
    def create(self, vals):
        new_lot = super(StockProductionLotInherit, self).create(vals)
        
        created_company_id = vals.get('company_id')
        company_ids_to_replicate = [1, 2, 3, 4]
        
        for company_id in company_ids_to_replicate:
            if created_company_id != company_id:
                new_lot.copy(default={'company_id': company_id})

        return new_lot
