# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_is_zero
import logging
_logger = logging.getLogger(__name__)

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
    _sql_constraints = [
        ("uniq_company", "unique(company_id)", "Solo puede existir 1 configuración por empresa."),
    ]

    def _compute_account_move_count(self):
        for rec in self:
            rec.account_move_count = len(rec.account_move_ids)
            
    def action_view_account_moves(self):
        self.ensure_one()
        return {
            "name": _("Asientos Contables de Cierre/Apertura de Gestión - %s") % self.company_id.display_name,
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
    # Botones de Cierre de Gestión y Apertura
    # ---------------------------
    def action_generate_management_closure_1_2_3(self):
        self.ensure_one()
        # validar que la fecha actual este 1 dia después de date_end para evitar generar asientos con fecha en el pasado
        #if fields.Date.to_date(self.date_end) >= fields.Date.today():
        #    raise UserError(_("La fecha de fin del período debe ser menor a la fecha actual para generar el asiento de cierre."))
        account_proveedor_ids = None
        account_client_ids = self.env['account.account'].search(['&',
                                                                    ('company_id', '=', self.company_id.id),
                                                                    '|', '|', 
                                                                        ('code', '=like', '1%'), 
                                                                        ('code', '=like', '2%'), 
                                                                        ('code', '=like', '3%')])
        # verificar si existe un asiento de cierre para cuentas 1-2-3, si existe no generar otro
        existing_move = self.env['account.move'].search([('company_id', '=', self.company_id.id),
                                                        ('fiscal_period_config_id', '=', self.id),
                                                        ('date', '=', self.date_end),
                                                        ('journal_id', '=', self.journal_id.id),
                                                        ('move_type', '=', 'entry'),
                                                        ('line_ids.account_id', 'in', account_client_ids.ids if account_client_ids else []),
                                                        ('state', '=', 'posted')], limit=1)
        #validar si existe el asiento 4-5 confirmado, si existe que le permita generar el asiento de cierre 1-2-3, sino no permitir generar el asiento de cierre 1-2-3
        existing_move_4_5 = self.env['account.move'].search([('company_id', '=', self.company_id.id),
                                                        ('fiscal_period_config_id', '=', self.id),
                                                        ('date', '=', self.date_end),
                                                        ('journal_id', '=', self.journal_id.id),
                                                        ('move_type', '=', 'entry'),
                                                        ('line_ids.account_id.code', '=like', '4%'),
                                                        ('line_ids.account_id.code', '=like', '5%'),
                                                        ('state', '=', 'posted')], limit=1)
        if not existing_move_4_5:
            raise ValidationError(_("Debe generar primero el asiento de cierre para cuentas 4-5."))
        
        if existing_move:
            raise ValidationError(_("Ya existe un asiento de cierre para cuentas 1-2-3 en este período. No se puede generar otro."))

        #generar el asiento de cierre
        move_vals_list = self._prepare_move_vals(account_client_ids, account_proveedor_ids)
        created_moves = self.env['account.move']
        for vals in move_vals_list:
            created_moves |= self.env['account.move'].create(vals)

        if not created_moves:
            raise ValidationError(_("No se generaron asientos de cierre."))

        # Si hay uno solo, abrir FORM directo al registro
        if len(created_moves) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Asiento Contable de Cierre de Periodo (4-5) - %s") % self.company_id.display_name,
                "res_model": "account.move",
                "view_mode": "form",
                "res_id": created_moves.id,
                "target": "current",
            }

        # Fallback: si por diseño se generan varios
        return {
            "type": "ir.actions.act_window",
            "name": _("Asientos Contables de Cierre de Periodo (4-5) - %s") % self.company_id.display_name,
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": [("id", "in", created_moves.ids)],
            "target": "current",
        }
        
    def action_generate_management_closure_4_5(self):
        self.ensure_one()

        account_client_ids = None
        account_proveedor_ids = self.env['account.account'].search(['&',
                                                                        ('company_id', '=', self.company_id.id), 
                                                                        '|', 
                                                                            ('code', '=like', '4%'), 
                                                                            ('code', '=like', '5%')])
        #verificar si existe un asiento de cierre para cuentas 4-5, si existe no generar otro
        existing_move = self.env['account.move'].search([('company_id', '=', self.company_id.id),
                                                        ('fiscal_period_config_id', '=', self.id),
                                                        ('date', '=', self.date_end),
                                                        ('journal_id', '=', self.journal_id.id),
                                                        ('move_type', '=', 'entry'),
                                                        ('line_ids.account_id', 'in', account_proveedor_ids.ids if account_proveedor_ids else []),
                                                        ('state', '=', 'posted')], limit=1)
        if existing_move:
            raise ValidationError(_("Ya existe un asiento de cierre para cuentas 4-5 en este período. No se puede generar otro."))
        
        #generar el asiento de cierre
        _logger.info("Generando asiento de cierre para cuentas 4-5 del período %s - %s", self.date_start, self.date_end)
        _logger.info("Cuentas proveedor para cierre 4-5: %s", account_proveedor_ids)
        move_vals_list = self._prepare_move_vals(account_client_ids, account_proveedor_ids)
        created_moves = self.env['account.move']
        _logger.info("move_vals_list: %s", move_vals_list)
        for vals in move_vals_list:
            created_moves |= self.env['account.move'].create(vals)
        _logger.info("created_moves: %s", created_moves)
        if not created_moves:
            raise ValidationError(_("No se generaron asientos de cierre."))
        # Si hay uno solo, abrir FORM directo al registro
        if len(created_moves) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Asiento Contable de Cierre de Periodo (4-5) - %s") % self.company_id.display_name,
                "res_model": "account.move",
                "view_mode": "form",
                "res_id": created_moves.id,
                "target": "current",
            }

        # Fallback: si por diseño se generan varios
        return {
            "type": "ir.actions.act_window",
            "name": _("Asientos Contables de Cierre de Periodo (4-5) - %s") % self.company_id.display_name,
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": [("id", "in", created_moves.ids)],
            "target": "current",
        }
        
    def action_generate_opening_entries(self):
        self.ensure_one()
        # validar que la fecha actual este 1 dia después de date_end para evitar generar asientos con fecha en el pasado
        #if fields.Date.to_date(self.date_end) >= fields.Date.today():
        #    raise UserError(_("La fecha de fin del período debe ser menor a la fecha actual para generar el asiento de apertura."))
        account_client_ids = self.env['account.account'].search(['&',
                                                                    ('company_id', '=', self.company_id.id),
                                                                    '|', '|', 
                                                                        ('code', '=like', '1%'), 
                                                                        ('code', '=like', '2%'), 
                                                                        ('code', '=like', '3%')])
        if not account_client_ids:
            raise ValidationError(_("No se encontraron cuentas 1-2-3 para generar el asiento de apertura."))
        account_move = self.env['account.move'].search([('company_id', '=', self.company_id.id),
                                                        ('fiscal_period_config_id', '=', self.id),
                                                        ('date', '=', self.date_end),
                                                        ('journal_id', '=', self.journal_id.id),
                                                        ('move_type', '=', 'entry'),
                                                        ('line_ids.account_id', 'in', account_client_ids.ids if account_client_ids else []),
                                                        ('state', '=', 'posted')], limit=1)
        if not account_move:
            raise ValidationError(_("No existe asiento de cierre para cuentas 1-2-3. No se puede generar el asiento de apertura."))
        
        date = fields.Date.to_date(self.date_end) + timedelta(days=1) # la fecha de apertura es un día después de la fecha de cierre
        line_ids = []
        for line in account_move.line_ids:
            if account_client_ids and line.account_id in account_client_ids:
                # invertir el saldo del asiento de cierre para la apertura
                debit = line.credit
                credit = line.debit
                line_ids.append((0, 0, {
                    "name": _("Apertura - %s") % line.account_id.display_name,
                    "account_id": line.account_id.id,
                    "debit": debit,
                    "credit": credit,
                }))
        #generar el asiento de apertura
        move_vals = {
            "move_type": "entry",
            "company_id": self.company_id.id,
            "date": date,
            "journal_id": self.journal_id.id,
            "ref": _("Apertura de periodo de %s") % self.company_id.display_name,
            "fiscal_period_config_id": self.id,
            "line_ids": line_ids,
            
        }
        self.env["account.move"].create(move_vals)
        return {
            "name": _("Asiento Contable de Apertura de Periodo - %s") % self.company_id.display_name,
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
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

    def _prepare_move_vals(self, account_client_ids=None, account_proveedor_ids=None):
        self.ensure_one()
        account_moves = []
        account_moves = self.closed_gestion_move_exists(account_client_ids, account_proveedor_ids, account_moves)
        return account_moves

    def _base_domain(self):
        self.ensure_one()
        dom = [
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"),
        ]
        return dom

    def closed_gestion_move_exists(self, account_client_ids, account_proveedor_ids, account_moves):
        AML = self.env["account.move.line"].with_context(active_test=False)
        currency = self.company_id.currency_id
        base = self._base_domain()
        if account_client_ids:
            base = self._base_domain() + [("account_id", "in", account_client_ids.ids)]
            dom_initial = base + [("date", "<", self.date_start)]
            dom_period = base + [("date", ">=", self.date_start), ("date", "<=", self.date_end)]

            initial = AML.read_group(dom_initial, ["balance"], ["account_id"])
            period = AML.read_group(dom_period, ["debit", "credit", "balance"], ["account_id"])

            init_map = {x["account_id"][0]: (x.get("balance", 0.0) or 0.0) for x in initial if x.get("account_id")}
            per_map = {x["account_id"][0]: x for x in period if x.get("account_id")}

            account_ids_all = set(init_map) | set(per_map)
            accounts = self.env["account.account"].browse(list(account_ids_all)).sorted(lambda a: (a.code or "", a.id))

            line_vals = []
            total_debit = 0.0
            total_credit = 0.0

            for acc in accounts:
                initial_balance = init_map.get(acc.id, 0.0)
                debit_p = per_map.get(acc.id, {}).get("debit", 0.0) or 0.0
                credit_p = per_map.get(acc.id, {}).get("credit", 0.0) or 0.0
                period_balance = per_map.get(acc.id, {}).get("balance", 0.0)
                if period_balance is None:
                    period_balance = debit_p - credit_p

                ending_balance = currency.round(initial_balance + period_balance)

                # Línea opuesta para dejar la cuenta en cero
                debit = currency.round(-ending_balance if ending_balance < 0 else 0.0)
                credit = currency.round(ending_balance if ending_balance > 0 else 0.0)

                if float_is_zero(debit - credit, precision_rounding=currency.rounding):
                    continue

                line_vals.append((0, 0, {
                    "name": _("Cierre - %s") % acc.display_name,
                    "account_id": acc.id,
                    "debit": debit,
                    "credit": credit,
                }))
                total_debit += debit
                total_credit += credit

            # Contrapartida UNA sola vez, al final
            diff = currency.round(total_debit - total_credit)
            if not float_is_zero(diff, precision_rounding=currency.rounding):
                # Si diff > 0 sobran débitos => agregar crédito
                # Si diff < 0 sobran créditos => agregar débito
                line_vals.append((0, 0, {
                    "name": _("Contrapartida cierre - %s") % self.equity_account_id.display_name,
                    "account_id": self.equity_account_id.id,
                    "debit": currency.round(-diff if diff < 0 else 0.0),
                    "credit": currency.round(diff if diff > 0 else 0.0),
                }))
                total_debit += currency.round(-diff if diff < 0 else 0.0)
                total_credit += currency.round(diff if diff > 0 else 0.0)

            # Validación final defensiva
            final_diff = currency.round(total_debit - total_credit)
            if not float_is_zero(final_diff, precision_rounding=currency.rounding):
                raise ValueError(_("Asiento desbalanceado residual: %s") % final_diff)

            account_moves.append({
                "move_type": "entry",
                "company_id": self.company_id.id,
                "date": self.date_end,
                "journal_id": self.journal_id.id,
                "ref": _("Cierre de Periodo - %s") % (self.company_id.display_name),
                "fiscal_period_config_id": self.id,
                "line_ids": line_vals,
            }) 
        if account_proveedor_ids:
            base = self._base_domain() + [("account_id", "in", account_proveedor_ids.ids)]
            dom_initial = base + [("date", "<", self.date_start)]
            dom_period = base + [("date", ">=", self.date_start), ("date", "<=", self.date_end)]

            initial = AML.read_group(dom_initial, ["balance"], ["account_id"])
            period = AML.read_group(dom_period, ["debit", "credit", "balance"], ["account_id"])

            init_map = {x["account_id"][0]: (x.get("balance", 0.0) or 0.0) for x in initial if x.get("account_id")}
            per_map = {x["account_id"][0]: x for x in period if x.get("account_id")}

            account_ids_all = set(init_map) | set(per_map)
            accounts = self.env["account.account"].browse(list(account_ids_all)).sorted(lambda a: (a.code or "", a.id))

            line_vals = []
            total_debit = 0.0
            total_credit = 0.0

            for acc in accounts:
                initial_balance = init_map.get(acc.id, 0.0)
                debit_p = per_map.get(acc.id, {}).get("debit", 0.0) or 0.0
                credit_p = per_map.get(acc.id, {}).get("credit", 0.0) or 0.0
                period_balance = per_map.get(acc.id, {}).get("balance", 0.0)
                if period_balance is None:
                    period_balance = debit_p - credit_p

                ending_balance = currency.round(initial_balance + period_balance)

                # Línea opuesta para dejar la cuenta en cero
                debit = currency.round(-ending_balance if ending_balance < 0 else 0.0)
                credit = currency.round(ending_balance if ending_balance > 0 else 0.0)

                if float_is_zero(debit - credit, precision_rounding=currency.rounding):
                    continue

                line_vals.append((0, 0, {
                    "name": _("Cierre - %s") % acc.display_name,
                    "account_id": acc.id,
                    "debit": debit,
                    "credit": credit,
                }))
                total_debit += debit
                total_credit += credit

            # Contrapartida UNA sola vez, al final
            diff = currency.round(total_debit - total_credit)
            if not float_is_zero(diff, precision_rounding=currency.rounding):
                # Si diff > 0 sobran débitos => agregar crédito
                # Si diff < 0 sobran créditos => agregar débito
                line_vals.append((0, 0, {
                    "name": _("Contrapartida cierre - %s") % self.equity_account_id.display_name,
                    "account_id": self.equity_account_id.id,
                    "debit": currency.round(-diff if diff < 0 else 0.0),
                    "credit": currency.round(diff if diff > 0 else 0.0),
                }))
                total_debit += currency.round(-diff if diff < 0 else 0.0)
                total_credit += currency.round(diff if diff > 0 else 0.0)

            # Validación final defensiva
            final_diff = currency.round(total_debit - total_credit)
            if not float_is_zero(final_diff, precision_rounding=currency.rounding):
                raise ValueError(_("Asiento desbalanceado residual: %s") % final_diff)

            account_moves.append({
                "move_type": "entry",
                "company_id": self.company_id.id,
                "date": self.date_end,
                "journal_id": self.journal_id.id,
                "ref": _("Cierre de Periodo - %s") % (self.company_id.display_name),
                "fiscal_period_config_id": self.id,
                "line_ids": line_vals,
            }) 
        return account_moves