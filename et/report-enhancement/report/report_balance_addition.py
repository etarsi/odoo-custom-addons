from odoo import api, models


class ReportBalanceAddition(models.AbstractModel):
    _name = "report.enhancement.report_balance_addition_document"
    _description = "Balance de Sumas y Saldos (HTML/PDF)"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["report.balance.addition.wizard"].browse(docids[:1])
        lines, totals = wizard._get_lines()
        return {
            "doc_ids": wizard.ids,
            "doc_model": wizard._name,
            "docs": wizard,
            "company": wizard.company_id,
            "currency": wizard.company_id.currency_id,
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "lines": lines,
            "totals": totals,
        }
