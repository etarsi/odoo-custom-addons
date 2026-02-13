# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
from odoo.exceptions import AccessError, UserError, ValidationError
import logging, json
from datetime import date, datetime
from odoo.tools.misc import format_date, format_amount
from odoo.tools.float_utils import float_round, float_is_zero
import base64
_logger = logging.getLogger(__name__)


class SaleOrderInherit(models.Model):
    _inherit = "sale.order"

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

    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        journal = self.env['account.move'].with_context(default_move_type='out_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the company %s (%s).', self.company_id.name, self.company_id.id))
        
        WmsCode = self.env['wms.code']
        wms_codes = set()
        if self.picking_ids:
            for p in self.picking_ids:
                if p.codigo_wms:
                    wms_codes.add(p.codigo_wms)
        
        wms_code_records = WmsCode.search([('name', 'in', list(wms_codes))])
        existing_names = set(wms_code_records.mapped('name'))
        missing_names = wms_codes - existing_names
        
        new_records = WmsCode.create([{'name': name} for name in missing_names])
        wms_records = wms_code_records | new_records

        invoice_vals = {
            'ref': self.client_order_ref or '',
            'move_type': 'out_invoice',
            'narration': self.note,
            'currency_id': self.pricelist_id.currency_id.id,
            'campaign_id': self.campaign_id.id,
            'medium_id': self.medium_id.id,
            'source_id': self.source_id.id,
            'user_id': self.user_id.id,
            'invoice_user_id': self.user_id.id,
            'team_id': self.team_id.id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id.get_fiscal_position(self.partner_invoice_id.id)).id,
            'partner_bank_id': self.company_id.partner_id.bank_ids.filtered(lambda bank: bank.company_id.id in (self.company_id.id, False))[:1].id,
            'journal_id': journal.id,  # company comes from the journal
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'payment_reference': self.reference,
            'transaction_ids': [(6, 0, self.transaction_ids.ids)],
            'invoice_line_ids': [],
            'company_id': self.company_id.id,
        }
        return invoice_vals
    
    def action_open_refacturar_wizard(self):
        self.ensure_one()
        action = self.env.ref('account_enhancement.action_open_sale_refacturar_account_wizard').read()[0]
        # Pasar el pedido por defecto al wizard
        action['context'] = dict(self.env.context, default_sale_id=self.id)
        return action    




class SaleOrderLineInherit(models.Model):
    _inherit = "sale.order.line"

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
