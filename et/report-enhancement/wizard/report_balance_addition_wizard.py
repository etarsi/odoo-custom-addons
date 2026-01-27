from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import date_utils


class ReportBalanceAdditionWizard(models.TransientModel):
    """Reporte de Suma y Saldo."""

    _name = "report.balance.addition.wizard"
    _description = "Reporte de Suma y Saldo"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    account_ids = fields.Many2many(
        comodel_name="account.account", string="Filter accounts"
    )
    hide_account_at_0 = fields.Boolean(
        string="Hide accounts at 0",
        default=True,
        help="When this option is enabled, the trial balance will "
        "not display accounts that have initial balance = "
        "debit = credit = end balance = 0",
    )
    partner_ids = fields.Many2many(comodel_name="res.partner", string="Filter partners")
    journal_ids = fields.Many2many(comodel_name="account.journal")

    def _export(self, report_type):
        """Default export is PDF."""
        return self._print_report(report_type)

    def button_export_html(self):
        """Export the report in HTML format."""
        return self._export("html")
    
    def button_export_pdf(self):
        """Export the report in PDF format."""
        return self._export("pdf")
    
    def button_export_xlsx(self):
        """Export the report in XLSX format."""
        return self._export("xlsx")