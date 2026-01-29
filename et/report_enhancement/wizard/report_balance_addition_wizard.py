from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import date_utils


class ReportBalanceAdditionWizard(models.TransientModel):
    """Reporte de Suma y Saldo."""

    _name = "report.balance.addition.wizard"
    _description = "Reporte de Suma y Saldo"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(required=True, string="Fecha desde", default=lambda self: date_utils.start_of(self.env.context.get('date') or fields.Date.today(), 'year'))
    date_to = fields.Date(required=True, string="Fecha hasta", default=lambda self: date_utils.end_of(self.env.context.get('date') or fields.Date.today(), 'year'))
    account_ids = fields.Many2many(
        comodel_name="account.account", string="Filtrar cuentas"
    )
    hide_account_at_0 = fields.Boolean(
        string="Ocultar cuentas en 0",
        default=True,
        help="Cuando esta opción está habilitada, el balance de prueba no mostrará cuentas que tengan saldo inicial = debe = haber = saldo final = 0",
    )
    partner_ids = fields.Many2many(comodel_name="res.partner", string="Filtrar socios")
    journal_ids = fields.Many2many(comodel_name="account.journal", string="Filtrar diarios")
    
    
    
    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Reset journals when company changes."""
        self.journal_ids = False
        self.account_ids = False
        #----------------------------- default journals of the company
        if self.company_id:
            #que sea domain igual a company_id, sea como un filtro visual
            return {'domain': {'journal_ids': [('company_id', '=', self.company_id.id)],
                               'account_ids': [('company_id', '=', self.company_id.id)]}}
            

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
    
    
    # -----------------------------
    # Report dispatch
    # -----------------------------
    def _print_report(self, report_type):
        self.ensure_one()
        data = {"form": self.read([
            "company_id","date_from","date_to",
            "account_ids","partner_ids","journal_ids",
            "hide_account_at_0"
        ])[0]}
        if report_type == "html":
            return self.env.ref("report_enhancement.report_balance_addition_html").report_action(self, data=data)
        if report_type == "pdf":
            return self.env.ref("report_enhancement.report_balance_addition_pdf").report_action(self, data=data)
        if report_type == "xlsx":
            return self.env.ref("report_enhancement.report_balance_addition_xlsx").report_action(self, data=data)

    # -----------------------------
    # Data builder (sumas y saldos)
    # -----------------------------
    def _base_domain(self):
        self.ensure_one()
        dom = [
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"),  # como balance estándar (solo asientos posteados)
        ]
        if self.account_ids:
            dom.append(("account_id", "in", self.account_ids.ids))
        if self.partner_ids:
            dom.append(("partner_id", "in", self.partner_ids.ids))
        if self.journal_ids:
            dom.append(("journal_id", "in", self.journal_ids.ids))
        return dom

    @staticmethod
    def _split_balance(balance):
        """Devuelve (debe, haber) desde un balance (debit-credit)."""
        if balance >= 0:
            return balance, 0.0
        return 0.0, -balance

    def _get_lines(self):
        self.ensure_one()
        AML = self.env["account.move.line"].with_context(active_test=False)

        base = self._base_domain()  # ojo: que respete target_move posted/all si lo agregás
        dom_initial = base + [("date", "<", self.date_from)]
        dom_period  = base + [("date", ">=", self.date_from), ("date", "<=", self.date_to)]

        initial = AML.read_group(dom_initial, ["balance"], ["account_id"])
        period  = AML.read_group(dom_period,  ["debit", "credit", "balance"], ["account_id"])

        init_map = {x["account_id"][0]: x.get("balance", 0.0) for x in initial if x.get("account_id")}
        per_map  = {x["account_id"][0]: x for x in period if x.get("account_id")}

        account_ids = set(init_map) | set(per_map)
        accounts = self.env["account.account"].browse(list(account_ids)).sorted(lambda a: (a.code, a.id))

        lines = []
        totals = {"initial_balance": 0.0, "debit": 0.0, "credit": 0.0, "period_balance": 0.0, "ending_balance": 0.0}

        for acc in accounts:
            initial_balance = init_map.get(acc.id, 0.0)
            debit = per_map.get(acc.id, {}).get("debit", 0.0) or 0.0
            credit = per_map.get(acc.id, {}).get("credit", 0.0) or 0.0
            period_balance = per_map.get(acc.id, {}).get("balance", 0.0) or (debit - credit)
            ending_balance = initial_balance + period_balance

            if self.hide_account_at_0 and (
                abs(initial_balance) < 1e-9 and abs(debit) < 1e-9 and abs(credit) < 1e-9 and abs(ending_balance) < 1e-9
            ):
                continue

            lines.append({
                "account_code": acc.code,
                "account_name": acc.name,
                "initial_balance": initial_balance,
                "debit": debit,
                "credit": credit,
                "period_balance": period_balance,
                "ending_balance": ending_balance,
            })

            totals["initial_balance"] += initial_balance
            totals["debit"] += debit
            totals["credit"] += credit
            totals["period_balance"] += period_balance
            totals["ending_balance"] += ending_balance

        return lines, totals