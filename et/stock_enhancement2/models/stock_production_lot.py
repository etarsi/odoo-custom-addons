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
        if not self.env.context.get('skip_lot_replication'):
            company_ids_to_replicate = [1, 2, 3, 4]
            created_company_id = vals.get('company_id')
            
            companies_to_copy = [
                id for id in company_ids_to_replicate if id != created_company_id
            ]

            vals_for_copy = dict(vals, **{'context': {'skip_lot_replication': True}})
            
            for company_id in companies_to_copy:
                vals_for_copy['company_id'] = company_id
                super(StockProductionLotInherit, self).create(vals_for_copy)

        return super(StockProductionLotInherit, self).create(vals)
