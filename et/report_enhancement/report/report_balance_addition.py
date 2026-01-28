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
        
    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        wiz = self.env["report.balance.addition.wizard"].browse((docids or [self.env.context.get("active_id")])[0])
        if not wiz:
            active_id = self.env.context.get("active_id")
            wiz = self.env["report.balance.addition.wizard"].browse(active_id) if active_id else self.env["report.balance.addition.wizard"]
        company = wiz.company_id
        # Dominio común para drill-down (clic en importes)
        aml_domain_common = [("company_id", "=", company.id), ("parent_state", "=", "posted")]
        if wiz.account_ids:
            aml_domain_common.append(("account_id", "in", wiz.account_ids.ids))
        if wiz.partner_ids:
            aml_domain_common.append(("partner_id", "in", wiz.partner_ids.ids))
        if wiz.journal_ids:
            aml_domain_common.append(("journal_id", "in", wiz.journal_ids.ids))

        # Calcular trial_balance como OCA (saldo firmado)
        AML = self.env["account.move.line"].with_context(active_test=False)

        dom_initial = aml_domain_common + [("date", "<", wiz.date_from)]
        dom_period  = aml_domain_common + [("date", ">=", wiz.date_from), ("date", "<=", wiz.date_to)]

        init_rg = AML.read_group(dom_initial, ["balance"], ["account_id"])
        per_rg  = AML.read_group(dom_period,  ["debit", "credit", "balance"], ["account_id"])

        init_map = {x["account_id"][0]: x.get("balance", 0.0) for x in init_rg if x.get("account_id")}
        per_map  = {x["account_id"][0]: x for x in per_rg if x.get("account_id")}

        account_ids = set(init_map.keys()) | set(per_map.keys())
        accounts = self.env["account.account"].browse(list(account_ids)).sorted(lambda a: (a.code, a.id))

        trial_balance = []
        for acc in accounts:
            initial_balance = init_map.get(acc.id, 0.0)
            debit = (per_map.get(acc.id, {}) or {}).get("debit", 0.0) or 0.0
            credit = (per_map.get(acc.id, {}) or {}).get("credit", 0.0) or 0.0
            balance = (per_map.get(acc.id, {}) or {}).get("balance", 0.0)
            if balance is None:
                balance = debit - credit
            ending_balance = initial_balance + balance

            if wiz.hide_account_at_0 and (
                abs(initial_balance) < 1e-9 and abs(debit) < 1e-9 and abs(credit) < 1e-9 and abs(ending_balance) < 1e-9
            ):
                continue

            trial_balance.append({
                "type": "account_type",
                "id": acc.id,
                "code": acc.code,
                "name": acc.name,
                "initial_balance": initial_balance,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "ending_balance": ending_balance,
                "level": 0,
            })

        return {
            "docs": wiz,                 # en tu wrapper lo iterás como o
            "o": wiz,                    # opcional
            "res_company": company,      # usado en t-options display_currency
            "date_from": wiz.date_from,
            "date_to": wiz.date_to,
            "hide_account_at_0": wiz.hide_account_at_0,

            "trial_balance": trial_balance,
            "aml_domain_common": aml_domain_common,

            # Flags que tu QWeb usa en t-if
            "show_partner_details": False,
            "foreign_currency": False,
            "show_hierarchy": False,
            "limit_hierarchy_level": False,
            "show_hierarchy_level": 0,
            "hide_parent_hierarchy_level": False,
        }