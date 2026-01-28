from odoo import api, models
from odoo.tools.misc import formatLang as _formatLang
import logging
_logger = logging.getLogger(__name__)


class ReportBalanceAddition(models.AbstractModel):
    _name = "report.report_enhancement.report_balance_addition"
    _description = "Balance de Sumas y Saldos (HTML/PDF)"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        wiz = self.env["report.balance.addition.wizard"].browse((docids or [self.env.context.get("active_id")])[0])

        lines, totals = wiz._get_lines()
        currency = wiz.company_id.currency_id

        return {
            "docs": wiz,
            "company": wiz.company_id,
            "currency": currency,
            "date_from": wiz.date_from,
            "date_to": wiz.date_to,
            "lines": lines,
            "totals": totals,

            # 🔥 asegura que formatLang sea función
            "formatLang": lambda amount, currency_obj=None: _formatLang(
                self.env, amount, currency_obj=(currency_obj or currency)
            ),
        }