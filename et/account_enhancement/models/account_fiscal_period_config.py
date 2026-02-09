# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class AccountFiscalPeriodConfig(models.Model):
    _name = "account.fiscal.period.config"
    _description = "Ejercicio de Cierre y Apertura"
    _rec_name = "company_id"
    _order = "company_id"

    company_id = fields.Many2one(
        "res.company", required=True, ondelete="cascade",
        default=lambda self: self.env.company, index=True
    )
    date_start = fields.Date(required=True, default=lambda self: fields.Date.to_string(fields.Date.today().replace(month=1, day=1)))
    date_end = fields.Date(required=True, default=lambda self: fields.Date.to_string(fields.Date.today().replace(month=12, day=31)))
    state = fields.Selection(
        [("draft", "Borrador"), 
        ("open", "Gestión Activa"),
        ("closed", "Gestión Finalizada"),
        ("archived", "Archivada")],
        default="draft", required=True)
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario de Cierre/Apertura",
        required=True,
        domain="[('company_id','=',company_id),('type','=','general')]",
    )




    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError(_("La fecha inicio no puede ser mayor que fecha fin."))

    def _validate_no_overlap(self):
        for rec in self:
            if not rec.date_start or not rec.date_end:
                continue
            overlapping = self.search([
                ("id", "!=", rec.id),
                ("company_id", "=", rec.company_id.id),
                ("state", "!=", "archived"),
                ("date_start", "<=", rec.date_end),
                ("date_end", ">=", rec.date_start),
            ], limit=1)
            if overlapping:
                raise ValidationError(_("El período se superpone con otro período existente (%s - %s).") % (overlapping.date_start, overlapping.date_end))

    def unlink(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Solo se pueden eliminar períodos en estado Borrador."))
        return super().unlink()
    
    def write(self, vals):
        res = super().write(vals)
        if "date_start" in vals or "date_end" in vals:
            self._validate_no_overlap()
        return res
    
    def create(self, vals):
        rec = super().create(vals)
        rec._validate_no_overlap()
        return rec
    
    # ---------------------------
    # API utilitaria para bloqueos
    # ---------------------------
    @api.model
    def is_locked(self, company_id, check_date):
        if not company_id or not check_date:
            return False
        d = fields.Date.to_date(check_date)
        conf = self.search([
            ("company_id", "=", company_id),
            ("state", "=", "closed"),
            ("date_start", "<=", d),
            ("date_end", ">=", d),
        ], limit=1)
        return bool(conf)

    @api.model
    def check_locked_or_raise(self, company_id, check_date, operation, model_label):
        # Los gestores de cierre pueden bypass
        if self.env.user.has_group("account_fiscal_close_open.group_fiscal_close_open_manager"):
            return

        if self.is_locked(company_id, check_date):
            raise UserError(_(
                "No se puede %(op)s en %(model)s.\n"
                "Período contable cerrado para la fecha %(date)s."
            ) % {
                "op": operation,
                "model": model_label,
                "date": fields.Date.to_string(fields.Date.to_date(check_date)),
            })

    # ---------------------------
    # Botones de Cierre de Gestión
    # ---------------------------
    def action_generate_management_closure(self):
        self.write({"state": "open"})
        return True

    # ---------------------------
    # Asientos apertura / cierre
    # ---------------------------
    def _group_balances(self, domain):
        """Devuelve lista (account_id, balance) usando account.move.line.balance."""
        aml = self.env["account.move.line"]
        rows = aml.read_group(
            domain=domain,
            fields=["balance:sum", "account_id"],
            groupby=["account_id"],
            lazy=False
        )
        result = []
        for r in rows:
            if not r.get("account_id"):
                continue
            account_id = r["account_id"][0]
            balance = r.get("balance", 0.0) or 0.0
            if abs(balance) > 0.0000001:
                result.append((account_id, balance))
        return result

    def _prepare_opening_move_vals(self):
        """Apertura al date_start: saldos BS acumulados hasta date_start - 1 día."""
        self.ensure_one()
        prev_day = self.date_start - timedelta(days=1)

        balances = self._group_balances([
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"),
            ("date", "<=", prev_day),
            ("account_id.internal_group", "in", ("asset", "liability", "equity")),
            ("account_id.deprecated", "=", False),
        ])

        line_vals = []
        total_balance = 0.0
        for account_id, bal in balances:
            total_balance += bal
            debit = bal if bal > 0 else 0.0
            credit = -bal if bal < 0 else 0.0
            line_vals.append((0, 0, {
                "name": _("Apertura"),
                "account_id": account_id,
                "debit": debit,
                "credit": credit,
            }))

        # Si por datos inconsistentes no balancea, ajusta contra cuenta patrimonial definida
        if abs(total_balance) > 0.0000001:
            line_vals.append((0, 0, {
                "name": _("Ajuste de apertura"),
                "debit": -total_balance if total_balance < 0 else 0.0,
                "credit": total_balance if total_balance > 0 else 0.0,
            }))

        return {
            "move_type": "entry",
            "company_id": self.company_id.id,
            "date": self.date_start,
            "journal_id": self.journal_id.id,
            "ref": _("Apertura %s") % self.company_id.display_name,
            "line_ids": line_vals,
        }

    def _prepare_closing_move_vals(self):
        """Cierre al date_end: cierra ingresos/gastos del período a cuenta patrimonial."""
        self.ensure_one()

        balances = self._group_balances([
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"),
            ("date", ">=", self.date_start),
            ("date", "<=", self.date_end),
            ("account_id.internal_group", "in", ("income", "expense")),
            ("account_id.deprecated", "=", False),
        ])

        line_vals = []
        total_pl = 0.0
        for account_id, bal in balances:
            total_pl += bal
            # Línea opuesta para dejar la cuenta P&L en cero
            debit = -bal if bal < 0 else 0.0
            credit = bal if bal > 0 else 0.0
            line_vals.append((0, 0, {
                "name": _("Cierre"),
                "account_id": account_id,
                "debit": debit,
                "credit": credit,
            }))

        if abs(total_pl) > 0.0000001:
            # Contrapartida a cuenta patrimonial
            line_vals.append((0, 0, {
                "name": _("Resultado del ejercicio"),
                "debit": total_pl if total_pl > 0 else 0.0,
                "credit": -total_pl if total_pl < 0 else 0.0,
            }))

        return {
            "move_type": "entry",
            "company_id": self.company_id.id,
            "date": self.date_end,
            "journal_id": self.journal_id.id,
            "ref": _("Cierre %s") % self.company_id.display_name,
            "line_ids": line_vals,
        }