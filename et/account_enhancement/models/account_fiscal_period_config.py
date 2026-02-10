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
        "res.company", string="Compañía", required=True, ondelete="cascade",
        default=lambda self: self.env.company, index=True
    )
    date_start = fields.Date(string="Fecha Inicio", required=True, default=lambda self: fields.Date.to_string(fields.Date.today().replace(month=1, day=1)), index=True)
    date_end = fields.Date(string="Fecha Fin", required=True, default=lambda self: fields.Date.to_string(fields.Date.today().replace(month=12, day=31)), index=True)
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario de Cierre/Apertura",
        required=True,
        domain="[('company_id','=',company_id),('type','=','general')]",
    )
    equity_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de Patrimonio para Resultado del Ejercicio",
        required=True,
        domain="[('company_id','=',company_id),('deprecated','=',False),('internal_type','=','other')]",
    )
    account_move_ids = fields.One2many("account.move", "fiscal_period_config_id", string="Asientos de Cierre/Apertura", readonly=True)
    account_move_count = fields.Integer(string="Cantidad de Asientos de Cierre/Apertura", compute="_compute_account_move_count")
    
    #validar sql un registro por compañía 
    _sql = """
        CREATE UNIQUE INDEX account_fiscal_period_config_company_id_uniq ON account_fiscal_period_config (company_id) WHERE state != 'archived';
    """
    
    def _compute_account_move_count(self):
        for rec in self:
            rec.account_move_count = len(rec.account_move_ids)
            
    def action_view_account_moves(self):
        self.ensure_one()
        return {
            "name": _("Asientos de Cierre/Apertura"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": [("fiscal_period_config_id", "=", self.id)],
        }

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError(_("La fecha inicio no puede ser mayor que fecha fin."))

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
    # Botones de Cierre de Gestión y Apertura
    # ---------------------------
    def action_generate_management_closure(self):
        self.ensure_one()
        #generar el asiento de cierre
        move_vals = self._prepare_move_vals()
        if move_vals:
            for vals in move_vals:
                self.env["account.move"].create(vals)

        return {
            "name": _("Asiento de Apertura/Cierre de Gestión"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": [("fiscal_period_config_id", "=", self.id)],  
        }
    
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

    def _prepare_move_vals(self):
        """Cierre al date_end: cierra ingresos/gastos del período a cuenta patrimonial.
            CREAR 4 ASIENTOS CONTABLES 2 PARA CIERRE DE GESTIÓN Y 2 PARA APERTURA DEL SIGUIENTE PERÍODO UNO PARA CUENTAS DEL 1 AL 3 Y OTRO PARA CUENTAS DEL 4 AL 5"""
        self.ensure_one()    
        account_sale_ids = self.env['account.account'].search(['&',
                                                                    ('company_id', '=', self.company_id.id),
                                                                    '|', '|', 
                                                                        ('code', '=like', '1%'), 
                                                                        ('code', '=like', '2%'), 
                                                                        ('code', '=like', '3%')])
        account_expense_ids = self.env['account.account'].search(['&',
                                                                        ('company_id', '=', self.company_id.id), 
                                                                        '|', 
                                                                            ('code', '=like', '4%'), 
                                                                            ('code', '=like', '5%')])
        account_moves = []
        if account_sale_ids:
            balances = self._group_balances([
                ("company_id", "=", self.company_id.id),
                ("parent_state", "=", "posted"),
                ("date", ">=", self.date_start),
                ("date", "<=", self.date_end),
                ("account_id", "in", account_sale_ids.ids),
                ("account_id.deprecated", "=", False),
            ])
            if balances:
                line_vals = []
                total_pl = 0.0
                for account_id, bal in balances:
                    total_pl += bal
                    # Línea opuesta para dejar la cuenta P&L en cero
                    debit = -bal if bal < 0 else 0.0
                    credit = bal if bal > 0 else 0.0
                    line_vals.append((0, 0, {
                        "name": _("Cierre - %s") % self.env["account.account"].browse(account_id).display_name,
                        "account_id": account_id,
                        "debit": debit,
                        "credit": credit,
                    }))
                    
                if abs(total_pl) > 0.0000001:
                    # Contrapartida a cuenta patrimonial
                    line_vals.append((0, 0, {
                        "name": _("Resultado del ejercicio"),
                        "account_id": self.equity_account_id.id,
                        "debit": total_pl if total_pl > 0 else 0.0,
                        "credit": -total_pl if total_pl < 0 else 0.0,
                    }))

                account_moves.append({
                    "move_type": "entry",
                    "company_id": self.company_id.id,
                    "date": self.date_end,
                    "journal_id": self.journal_id.id,
                    "ref": _("Cierre de Gestión (Clientes) de %s") % self.company_id.display_name,
                    "fiscal_period_config_id": self.id,
                    "line_ids": line_vals,
                }) 
        if account_expense_ids:
            balances = self._group_balances([
                ("company_id", "=", self.company_id.id),
                ("parent_state", "=", "posted"),
                ("date", ">=", self.date_start),
                ("date", "<=", self.date_end),
                ("account_id", "in", account_expense_ids.ids),
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
                    "name": _("Cierre - %s") % self.env["account.account"].browse(account_id).display_name,
                    "account_id": account_id,
                    "debit": debit,
                    "credit": credit,
                }))
            
            if abs(total_pl) > 0.0000001:
                # Contrapartida a cuenta patrimonial
                line_vals.append((0, 0, {
                    "name": _("Resultado del ejercicio"),
                    "account_id": self.equity_account_id.id,
                    "debit": total_pl if total_pl > 0 else 0.0,
                    "credit": -total_pl if total_pl < 0 else 0.0,
                }))

            account_moves.append({
                "move_type": "entry",
                "company_id": self.company_id.id,
                "date": self.date_end,
                "journal_id": self.journal_id.id,
                "ref": _("Cierre de Gestión (Proveedores) de %s") % self.company_id.display_name,
                "fiscal_period_config_id": self.id,
                "line_ids": line_vals,
            }) 

        return account_moves