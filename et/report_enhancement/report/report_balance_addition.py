from odoo import api, models
import logging
_logger = logging.getLogger(__name__)


class ReportBalanceAddition(models.AbstractModel):
    _name = "report.report_enhancement.report_balance_addition"
    _description = "Balance de Sumas y Saldos (HTML/PDF)"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}

        wiz = None
        if docids:
            wiz = self.env["report.balance.addition.wizard"].browse(docids[0])
        elif data.get("context", {}).get("active_id"):
            wiz = self.env["report.balance.addition.wizard"].browse(data["context"]["active_id"])
        else:
            # cuando viene solo 'form' (típico)
            form = data.get("form") or {}
            wiz = self.env["report.balance.addition.wizard"].create({
                "company_id": form.get("company_id") and form["company_id"][0] or self.env.company.id,
                "date_from": form.get("date_from"),
                "date_to": form.get("date_to"),
                "hide_account_at_0": form.get("hide_account_at_0", True),
                "account_ids": [(6, 0, form.get("account_ids", []))],
                "partner_ids": [(6, 0, form.get("partner_ids", []))],
                "journal_ids": [(6, 0, form.get("journal_ids", []))],
            })

        lines, totals = wiz._get_lines()
        _logger.info("Report values generated for Balance Addition report wizard ID %s", wiz.id)
        _logger.info("wiz: %s", wiz)
        _logger.info("Lines: %s", lines)
        return {
            "docs": wiz,
            "company_id": wiz.company_id,
            "currency": wiz.company_id.currency_id,
            "date_from": wiz.date_from,
            "date_to": wiz.date_to,
            "lines": lines,
            "totals": totals,
        }