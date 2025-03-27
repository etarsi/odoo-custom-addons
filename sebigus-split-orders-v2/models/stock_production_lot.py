# Copyright 2021 Tecnativa - Carlos Roca
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import operator as operator_lib

from odoo import _, fields, models


class StockProductionLot(models.Model):
    _inherit = "stock.production.lot"

    company_origen = fields.Many2one('res.company', 'Compañia de compra')
