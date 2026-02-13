# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


# =========================================================
# SALE ORDER
# =========================================================
class SaleOrder(models.Model):
    _inherit = ["sale.order", "fiscal.lock.mixin"]

    fiscal_period_locked = fields.Boolean(
        string="Bloqueado por Gestión",
        compute="_compute_fiscal_period_locked",
        readonly=True,
    )

    @api.depends("company_id", "date_order")
    def _compute_fiscal_period_locked(self):
        for rec in self:
            rec.fiscal_period_locked = rec._is_locked_by_period(rec.company_id.id, rec.date_order)

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for vals in vals_list:
            v = self._normalize_exception_vals(vals)
            company_id = v.get("company_id") or self.env.company.id
            date_value = v.get("date_order") or fields.Datetime.now()
            self._raise_if_locked(company_id, date_value, "crear", self._description or self._name, vals=v)
            normalized.append(v)
        return super().create(normalized)

    def write(self, vals):
        vals = self._normalize_exception_vals(vals)
        for rec in self:
            rec._raise_if_locked(rec.company_id.id, rec.date_order, "modificar", rec._description or rec._name, rec=rec, vals=vals)
            target_company = vals.get("company_id", rec.company_id.id)
            target_date = vals.get("date_order", rec.date_order)
            rec._raise_if_locked(target_company, target_date, "modificar", rec._description or rec._name, rec=rec, vals=vals)
        return super().write(vals)

    def unlink(self):
        for rec in self:
            rec._raise_if_locked(rec.company_id.id, rec.date_order, "eliminar", rec._description or rec._name, rec=rec)
        return super().unlink()


class SaleOrderLine(models.Model):
    _inherit = ["sale.order.line", "fiscal.lock.mixin"]

    fiscal_period_locked = fields.Boolean(
        string="Bloqueado por Gestión",
        compute="_compute_fiscal_period_locked",
        readonly=True,
    )

    @api.depends("order_id.date_order", "order_id.company_id", "company_id")
    def _compute_fiscal_period_locked(self):
        for rec in self:
            company_id = rec.company_id.id or rec.order_id.company_id.id
            rec.fiscal_period_locked = rec._is_locked_by_period(company_id, rec.order_id.date_order)

    @api.model_create_multi
    def create(self, vals_list):
        SO = self.env["sale.order"]
        normalized = []
        for vals in vals_list:
            v = self._normalize_exception_vals(vals)
            order = SO.browse(v["order_id"]) if v.get("order_id") else False
            company_id = v.get("company_id") or (order.company_id.id if order else self.env.company.id)
            date_value = order.date_order if order else fields.Datetime.now()
            self._raise_if_locked(company_id, date_value, "crear", self._description or self._name, vals=v, parent=order)
            normalized.append(v)
        return super().create(normalized)

    def write(self, vals):
        SO = self.env["sale.order"]
        vals = self._normalize_exception_vals(vals)
        for rec in self:
            current_company = rec.company_id.id or rec.order_id.company_id.id
            current_date = rec.order_id.date_order
            rec._raise_if_locked(current_company, current_date, "modificar", rec._description or rec._name, rec=rec, vals=vals, parent=rec.order_id)

            target_order = SO.browse(vals["order_id"]) if vals.get("order_id") else rec.order_id
            target_company = vals.get("company_id") or (target_order.company_id.id if target_order else current_company)
            target_date = target_order.date_order if target_order else current_date
            rec._raise_if_locked(target_company, target_date, "modificar", rec._description or rec._name, rec=rec, vals=vals, parent=target_order)
        return super().write(vals)

    def unlink(self):
        for rec in self:
            company_id = rec.company_id.id or rec.order_id.company_id.id
            rec._raise_if_locked(company_id, rec.order_id.date_order, "eliminar", rec._description or rec._name, rec=rec, parent=rec.order_id)
        return super().unlink()


# =========================================================
# ACCOUNT MOVE
# =========================================================
class AccountMove(models.Model):
    _inherit = ["account.move", "fiscal.lock.mixin"]

    fiscal_period_locked = fields.Boolean(
        string="Bloqueado por Gestión",
        compute="_compute_fiscal_period_locked",
        readonly=True,
    )

    @api.depends("company_id", "date", "block_accounting")
    def _compute_fiscal_period_locked(self):
        for rec in self:
            by_date = rec._is_locked_by_period(rec.company_id.id, rec.date)
            by_flag = bool(getattr(rec, "block_accounting", False))
            rec.fiscal_period_locked = by_date or by_flag

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for vals in vals_list:
            v = self._normalize_exception_vals(vals)
            company_id = v.get("company_id") or self.env.company.id
            date_value = v.get("date") or fields.Date.context_today(self)
            self._raise_if_locked(company_id, date_value, "crear", self._description or self._name, vals=v)
            normalized.append(v)
        return super().create(normalized)

    def write(self, vals):
        vals = self._normalize_exception_vals(vals)
        for rec in self:
            rec._raise_if_block_accounting(rec, "modificar", rec=rec, vals=vals, parent=rec)
            rec._raise_if_locked(rec.company_id.id, rec.date, "modificar", rec._description or rec._name, rec=rec, vals=vals, parent=rec)

            target_company = vals.get("company_id", rec.company_id.id)
            target_date = vals.get("date", rec.date)
            rec._raise_if_locked(target_company, target_date, "modificar", rec._description or rec._name, rec=rec, vals=vals, parent=rec)
        return super().write(vals)

    def unlink(self):
        for rec in self:
            rec._raise_if_block_accounting(rec, "eliminar", rec=rec, parent=rec)
            rec._raise_if_locked(rec.company_id.id, rec.date, "eliminar", rec._description or rec._name, rec=rec, parent=rec)
        return super().unlink()


class AccountMoveLine(models.Model):
    _inherit = ["account.move.line", "fiscal.lock.mixin"]

    fiscal_period_locked = fields.Boolean(
        string="Bloqueado por Gestión",
        compute="_compute_fiscal_period_locked",
        readonly=True,
    )

    @api.depends("company_id", "date", "move_id.date", "move_id.company_id", "move_id.block_accounting")
    def _compute_fiscal_period_locked(self):
        for rec in self:
            company_id = rec.company_id.id or rec.move_id.company_id.id
            date_value = rec.date or rec.move_id.date
            by_date = rec._is_locked_by_period(company_id, date_value)
            by_flag = bool(getattr(rec.move_id, "block_accounting", False))
            rec.fiscal_period_locked = by_date or by_flag

    @api.model_create_multi
    def create(self, vals_list):
        Move = self.env["account.move"]
        normalized = []
        for vals in vals_list:
            v = self._normalize_exception_vals(vals)
            move = Move.browse(v["move_id"]) if v.get("move_id") else False

            self._raise_if_block_accounting(move, "crear", vals=v, parent=move)

            company_id = v.get("company_id") or (move.company_id.id if move else self.env.company.id)
            date_value = v.get("date") or (move.date if move else fields.Date.context_today(self))
            self._raise_if_locked(company_id, date_value, "crear", self._description or self._name, vals=v, parent=move)

            normalized.append(v)
        return super().create(normalized)

    def write(self, vals):
        Move = self.env["account.move"]
        vals = self._normalize_exception_vals(vals)

        for rec in self:
            # Estado actual
            rec._raise_if_block_accounting(rec.move_id, "modificar", rec=rec, vals=vals, parent=rec.move_id)

            current_company = rec.company_id.id or rec.move_id.company_id.id
            current_date = rec.date or rec.move_id.date
            rec._raise_if_locked(current_company, current_date, "modificar", rec._description or rec._name, rec=rec, vals=vals, parent=rec.move_id)

            # Estado destino
            target_move = Move.browse(vals["move_id"]) if vals.get("move_id") else rec.move_id
            rec._raise_if_block_accounting(target_move, "modificar", rec=rec, vals=vals, parent=target_move)

            target_company = vals.get("company_id") or (target_move.company_id.id if target_move else current_company)
            target_date = vals.get("date") or (target_move.date if target_move else current_date)
            rec._raise_if_locked(target_company, target_date, "modificar", rec._description or rec._name, rec=rec, vals=vals, parent=target_move)

        return super().write(vals)

    def unlink(self):
        for rec in self:
            rec._raise_if_block_accounting(rec.move_id, "eliminar", rec=rec, parent=rec.move_id)

            company_id = rec.company_id.id or rec.move_id.company_id.id
            date_value = rec.date or rec.move_id.date
            rec._raise_if_locked(company_id, date_value, "eliminar", rec._description or rec._name, rec=rec, parent=rec.move_id)

        return super().unlink()


# =========================================================
# PURCHASE ORDER
# =========================================================
class PurchaseOrder(models.Model):
    _inherit = ["purchase.order", "fiscal.lock.mixin"]

    fiscal_period_locked = fields.Boolean(
        string="Bloqueado por Gestión",
        compute="_compute_fiscal_period_locked",
        readonly=True,
    )

    @api.depends("company_id", "date_order")
    def _compute_fiscal_period_locked(self):
        for rec in self:
            rec.fiscal_period_locked = rec._is_locked_by_period(rec.company_id.id, rec.date_order)

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for vals in vals_list:
            v = self._normalize_exception_vals(vals)
            company_id = v.get("company_id") or self.env.company.id
            date_value = v.get("date_order") or fields.Datetime.now()
            self._raise_if_locked(company_id, date_value, "crear", self._description or self._name, vals=v)
            normalized.append(v)
        return super().create(normalized)

    def write(self, vals):
        vals = self._normalize_exception_vals(vals)
        for rec in self:
            rec._raise_if_locked(rec.company_id.id, rec.date_order, "modificar", rec._description or rec._name, rec=rec, vals=vals)
            target_company = vals.get("company_id", rec.company_id.id)
            target_date = vals.get("date_order", rec.date_order)
            rec._raise_if_locked(target_company, target_date, "modificar", rec._description or rec._name, rec=rec, vals=vals)
        return super().write(vals)

    def unlink(self):
        for rec in self:
            rec._raise_if_locked(rec.company_id.id, rec.date_order, "eliminar", rec._description or rec._name, rec=rec)
        return super().unlink()


class PurchaseOrderLine(models.Model):
    _inherit = ["purchase.order.line", "fiscal.lock.mixin"]

    fiscal_period_locked = fields.Boolean(
        string="Bloqueado por Gestión",
        compute="_compute_fiscal_period_locked",
        readonly=True,
    )

    @api.depends("order_id.date_order", "order_id.company_id", "company_id")
    def _compute_fiscal_period_locked(self):
        for rec in self:
            company_id = rec.company_id.id or rec.order_id.company_id.id
            rec.fiscal_period_locked = rec._is_locked_by_period(company_id, rec.order_id.date_order)

    @api.model_create_multi
    def create(self, vals_list):
        PO = self.env["purchase.order"]
        normalized = []
        for vals in vals_list:
            v = self._normalize_exception_vals(vals)
            order = PO.browse(v["order_id"]) if v.get("order_id") else False
            company_id = v.get("company_id") or (order.company_id.id if order else self.env.company.id)
            date_value = order.date_order if order else fields.Datetime.now()
            self._raise_if_locked(company_id, date_value, "crear", self._description or self._name, vals=v, parent=order)
            normalized.append(v)
        return super().create(normalized)

    def write(self, vals):
        PO = self.env["purchase.order"]
        vals = self._normalize_exception_vals(vals)
        for rec in self:
            current_company = rec.company_id.id or rec.order_id.company_id.id
            current_date = rec.order_id.date_order
            rec._raise_if_locked(current_company, current_date, "modificar", rec._description or rec._name, rec=rec, vals=vals, parent=rec.order_id)

            target_order = PO.browse(vals["order_id"]) if vals.get("order_id") else rec.order_id
            target_company = vals.get("company_id") or (target_order.company_id.id if target_order else current_company)
            target_date = target_order.date_order if target_order else current_date
            rec._raise_if_locked(target_company, target_date, "modificar", rec._description or rec._name, rec=rec, vals=vals, parent=target_order)
        return super().write(vals)

    def unlink(self):
        for rec in self:
            company_id = rec.company_id.id or rec.order_id.company_id.id
            rec._raise_if_locked(company_id, rec.order_id.date_order, "eliminar", rec._description or rec._name, rec=rec, parent=rec.order_id)
        return super().unlink()


# =========================================================
# ACCOUNT PAYMENT
# =========================================================
class AccountPayment(models.Model):
    _inherit = ["account.payment", "fiscal.lock.mixin"]

    fiscal_period_locked = fields.Boolean(
        string="Bloqueado por Gestión",
        compute="_compute_fiscal_period_locked",
        readonly=True,
    )

    @api.depends("company_id", "date")
    def _compute_fiscal_period_locked(self):
        for rec in self:
            rec.fiscal_period_locked = rec._is_locked_by_period(rec.company_id.id, rec.date)

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for vals in vals_list:
            v = self._normalize_exception_vals(vals)
            company_id = v.get("company_id") or self.env.company.id
            date_value = v.get("date") or fields.Date.context_today(self)
            self._raise_if_locked(company_id, date_value, "crear", self._description or self._name, vals=v)
            normalized.append(v)
        return super().create(normalized)

    def write(self, vals):
        vals = self._normalize_exception_vals(vals)
        for rec in self:
            rec._raise_if_locked(rec.company_id.id, rec.date, "modificar", rec._description or rec._name, rec=rec, vals=vals)
            target_company = vals.get("company_id", rec.company_id.id)
            target_date = vals.get("date", rec.date)
            rec._raise_if_locked(target_company, target_date, "modificar", rec._description or rec._name, rec=rec, vals=vals)
        return super().write(vals)

    def unlink(self):
        for rec in self:
            rec._raise_if_locked(rec.company_id.id, rec.date, "eliminar", rec._description or rec._name, rec=rec)
        return super().unlink()


# =========================================================
# ACCOUNT PAYMENT GROUP
# =========================================================
class AccountPaymentGroup(models.Model):
    _inherit = ["account.payment.group", "fiscal.lock.mixin"]

    fiscal_period_locked = fields.Boolean(
        string="Bloqueado por Gestión",
        compute="_compute_fiscal_period_locked",
        readonly=True,
    )

    def _pg_date(self, rec=None, vals=None):
        vals = vals or {}
        return (
            vals.get("payment_date")
            or vals.get("date")
            or (getattr(rec, "payment_date", False) if rec else False)
            or (getattr(rec, "date", False) if rec else False)
        )

    def _compute_fiscal_period_locked(self):
        for rec in self:
            rec.fiscal_period_locked = rec._is_locked_by_period(rec.company_id.id, self._pg_date(rec=rec))

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for vals in vals_list:
            v = self._normalize_exception_vals(vals)
            company_id = v.get("company_id") or self.env.company.id
            date_value = self._pg_date(vals=v) or fields.Date.context_today(self)
            self._raise_if_locked(company_id, date_value, "crear", self._description or self._name, vals=v)
            normalized.append(v)
        return super().create(normalized)

    def write(self, vals):
        vals = self._normalize_exception_vals(vals)
        for rec in self:
            rec._raise_if_locked(rec.company_id.id, self._pg_date(rec=rec), "modificar", rec._description or rec._name, rec=rec, vals=vals)

            target_company = vals.get("company_id", rec.company_id.id)
            target_date = self._pg_date(rec=rec, vals=vals)
            rec._raise_if_locked(target_company, target_date, "modificar", rec._description or rec._name, rec=rec, vals=vals)
        return super().write(vals)

    def unlink(self):
        for rec in self:
            rec._raise_if_locked(rec.company_id.id, self._pg_date(rec=rec), "eliminar", rec._description or rec._name, rec=rec)
        return super().unlink()
