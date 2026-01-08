import time
from ast import literal_eval

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import date_utils


class GeneralLedgerReportWizard(models.TransientModel):
    """LIBRO MAYOR ENHANCENMENT."""

    _inherit = "general.ledger.report.wizard"

    def report_new(self):
        return False