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
        default_journals = self.env['account.journal'].search([('company_id', '=', self.company_id.id)], limit=3)
        self.journal_ids = default_journals

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
            "company_id", "date_from", "date_to",
            "account_ids", "partner_ids", "journal_ids",
            "hide_account_at_0",
        ])[0]}

        if report_type == "html":
            return self.env.ref("report_balance_addition_html").report_action(self, data=data)
        if report_type == "pdf":
            return self.env.ref("report_balance_addition_pdf").report_action(self, data=data)
        if report_type == "xlsx":
            return self.env.ref("report_balance_addition_xlsx").report_action(self, data=data)

        raise ValueError("Unknown report type: %s" % report_type)

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
        """Devuelve líneas por cuenta con saldo inicial, movimientos y saldo final (debe/haber)."""
        self.ensure_one()
        AML = self.env["account.move.line"].with_context(active_test=False)

        base = self._base_domain()
        dom_initial = base + [("date", "<", self.date_from)]
        dom_period = base + [("date", ">=", self.date_from), ("date", "<=", self.date_to)]

        # read_group por cuenta
        initial = AML.read_group(dom_initial, ["debit", "credit", "balance"], ["account_id"])
        period = AML.read_group(dom_period, ["debit", "credit", "balance"], ["account_id"])

        init_map = {
            x["account_id"][0]: {
                "debit": x.get("debit", 0.0),
                "credit": x.get("credit", 0.0),
                "balance": x.get("balance", 0.0),
            }
            for x in initial if x.get("account_id")
        }
        per_map = {
            x["account_id"][0]: {
                "debit": x.get("debit", 0.0),
                "credit": x.get("credit", 0.0),
                "balance": x.get("balance", 0.0),
            }
            for x in period if x.get("account_id")
        }

        account_ids = set(init_map.keys()) | set(per_map.keys())
        accounts = self.env["account.account"].browse(list(account_ids)).sorted(lambda a: (a.code, a.id))

        lines = []
        totals = {
            "initial_debit": 0.0, "initial_credit": 0.0,
            "period_debit": 0.0, "period_credit": 0.0,
            "ending_debit": 0.0, "ending_credit": 0.0,
        }

        for acc in accounts:
            ibal = init_map.get(acc.id, {}).get("balance", 0.0)
            pdebit = per_map.get(acc.id, {}).get("debit", 0.0)
            pcredit = per_map.get(acc.id, {}).get("credit", 0.0)
            pbal = per_map.get(acc.id, {}).get("balance", 0.0)

            initial_debit, initial_credit = self._split_balance(ibal)
            ending_debit, ending_credit = self._split_balance(ibal + pbal)

            if self.hide_account_at_0:
                if (
                    abs(initial_debit) < 1e-9 and abs(initial_credit) < 1e-9 and
                    abs(pdebit) < 1e-9 and abs(pcredit) < 1e-9 and
                    abs(ending_debit) < 1e-9 and abs(ending_credit) < 1e-9
                ):
                    continue

            line = {
                "account_code": acc.code,
                "account_name": acc.name,
                "initial_debit": initial_debit,
                "initial_credit": initial_credit,
                "period_debit": pdebit,
                "period_credit": pcredit,
                "ending_debit": ending_debit,
                "ending_credit": ending_credit,
            }
            lines.append(line)

            totals["initial_debit"] += initial_debit
            totals["initial_credit"] += initial_credit
            totals["period_debit"] += pdebit
            totals["period_credit"] += pcredit
            totals["ending_debit"] += ending_debit
            totals["ending_credit"] += ending_credit

        return lines, totals