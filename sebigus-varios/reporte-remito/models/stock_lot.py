from odoo import tools, models, fields, api, _
import base64
import logging
_logger = logging.getLogger(__name__)

class ProductionLot(models.Model):
    _inherit = "stock.production.lot"
    #company_id = fields.Many2many('res.company', 'Company', index=True, default=lambda self: self.env.company.id)
