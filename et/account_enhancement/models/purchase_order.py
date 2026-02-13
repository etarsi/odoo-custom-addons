# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
# =========================================================
# PURCHASE ORDER
# =========================================================
class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

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


class PurchaseOrderLineInherit(models.Model):
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
