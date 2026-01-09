import time
from ast import literal_eval

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import date_utils


class GeneralLedgerReportWizard(models.TransientModel):
    """LIBRO MAYOR ENHANCENMENT."""

    _inherit = "general.ledger.report.wizard"

    def buton_view_report_html_enhancement(self):
        """Genera el reporte en HTML del Libro Mayor."""
        self.ensure_one()
        data = self._prepare_report_general_ledger()
        return self.env.ref(
            "account_enhancement.action_print_report_general_ledger_html"
        ).report_action(self, data=data)