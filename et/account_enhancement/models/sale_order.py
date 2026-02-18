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

    period_cut_locked = fields.Boolean(string="Período de Corte Bloqueado", default=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("period_cut_locked"):
                raise ValidationError(_("No se puede crear un pedido con 'Período de Corte Bloqueado' activo."))
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            if vals.get("period_cut_locked") or rec.period_cut_locked:
                raise ValidationError(_("No se puede modificar un pedido con 'Período de Corte Bloqueado' activo."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.period_cut_locked:
                raise ValidationError(_("No se puede eliminar un pedido con 'Período de Corte Bloqueado' activo."))
        return super().unlink()
    
    def action_lock_period_cut(self):
        self.ensure_one()
        sql = """
            UPDATE sale_order
            SET period_cut_locked = TRUE
            WHERE id = %s
        """
        self.env.cr.execute(sql, (self.id,))

    def action_unlock_period_cut(self):
        self.ensure_one()
        sql = """
            UPDATE sale_order
            SET period_cut_locked = FALSE
            WHERE id = %s
        """
        self.env.cr.execute(sql, (self.id,))

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

    period_cut_locked = fields.Boolean(string="Período de Corte Bloqueado", related='order_id.period_cut_locked', store=True, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("period_cut_locked"):
                raise ValidationError(_("No se puede crear una línea de pedido con 'Período de Corte Bloqueado' activo."))  
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            if vals.get("period_cut_locked") or rec.period_cut_locked:
                raise ValidationError(_("No se puede modificar una línea de pedido con 'Período de Corte Bloqueado' activo."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.period_cut_locked:
                raise ValidationError(_("No se puede eliminar una línea de pedido con 'Período de Corte Bloqueado' activo."))
        return super().unlink()
