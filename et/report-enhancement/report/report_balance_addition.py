from odoo import api, models


class ReportBalanceAddition(models.AbstractModel):
    _name = "report_balance_addition"
    _description = "Balance de Sumas y Saldos (HTML/PDF)"

    @api.model
    def _get_report_values(self, docids, data=None):
        wiz = self.env["report.balance.addition.wizard"].browse(docids[:1])
        lines, totals = wiz._get_lines()
        return {
            "docs": wiz,
            "company": wiz.company_id,
            "currency": wiz.company_id.currency_id,
            "date_from": wiz.date_from,
            "date_to": wiz.date_to,
            "lines": lines,
            "totals": totals,
        }