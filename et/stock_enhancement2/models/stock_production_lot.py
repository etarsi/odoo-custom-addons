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
    
    _REPLICATION_CONTEXT_KEY = 'skip_lot_replication'

    @api.model
    def create(self, vals):
        if self.env.context.get(self._REPLICATION_CONTEXT_KEY):
            return super(StockProductionLotInherit, self).create(vals)
        
        new_lot = super(StockProductionLotInherit, self).create(vals)
        
        company_ids_to_replicate = [1, 2, 3, 4]
        created_company_id = new_lot.company_id.id
        
        companies_to_copy = [
            id for id in company_ids_to_replicate if id != created_company_id
        ]
        
        for company_id in companies_to_copy:
            
            original_name = new_lot.name
            
            default_vals = {
                'company_id': company_id,
                'name': original_name,
            }
            
            is_lot = self.env['stock.production.lot'].search([('name', '=', original_name), ('company_id', '=', company_id)])

            if not is_lot:
                new_lot.with_context(
                    **{self._REPLICATION_CONTEXT_KEY: True} 
                ).copy(default=default_vals)

        return new_lot
