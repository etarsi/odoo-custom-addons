# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
from odoo.exceptions import AccessError, UserError, ValidationError
import logging, json
from datetime import date, datetime
from odoo.tools.misc import format_date, format_amount
from odoo.tools.float_utils import float_compare
_logger = logging.getLogger(__name__)

class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    wms_code = fields.Char(string="Código WMS")
    executive_id = fields.Many2one(
        'res.users',
        string="Ejecutivo de Cuenta",
        related='partner_id.executive_id',
        store=True,
        readonly=True
    )
    picking_ids = fields.Many2many(
        'stock.picking',
        'stock_picking_invoice_rel',
        'invoice_id',
        'picking_id',
        string='Remitos relacionados'
    )
    date_paid = fields.Date(string="Fecha de pago", tracking=True)
    amount_total_day = fields.Float(string="Total del día", compute="_compute_amount_total_day")
    payment_refs_html = fields.Html(string="Ref de Pagos", compute="_compute_payment_html", sanitize=True)
    payment_amount_html = fields.Html(string="Montos de Cobro", compute="_compute_payment_html", sanitize=True)
    payment_date_html = fields.Html(string="Fecha de Pagos", compute="_compute_payment_html", sanitize=True)
    payment_refs_html_rp = fields.Html(string="Ref de Pagos", compute="_compute_payment_html_rp", sanitize=True)
    payment_amount_html_rp = fields.Html(string="Montos de Cobro", compute="_compute_payment_html_rp", sanitize=True)
    calendar_color_state = fields.Selection([
        ('paid', 'Pagado'),
        ('not_paid', 'No Pagado'),
    ], compute='_compute_calendar_color_state', store=False)

    total_amount_paid = fields.Float(string="Monto Pagado", compute="_compute_total_amount_paid")
   
    @api.model
    def create(self, vals):
        res = super().create(vals)
        #validar nota de credito sea de tipo comprobante nota de credito
        if res.move_type == 'out_refund':
            if res.l10n_latam_document_type_id.internal_type != 'credit_note' and res.l10n_latam_use_documents:
                raise ValidationError(_("Se esperaba una Nota de Crédito, pero el documento %s es de tipo %s.") % (
                    res.name,
                    res.l10n_latam_document_type_id.internal_type,
                ))
        return res

    def action_post(self):
        for move in self:
            if move.move_type == 'out_refund':
                if move.l10n_latam_document_type_id.internal_type != 'credit_note' and move.l10n_latam_use_documents:
                    raise ValidationError(_("Se esperaba una Nota de Crédito, pero el documento %s es de tipo %s.") % (
                        move.name,
                        move.l10n_latam_document_type_id.internal_type,
                    ))
        return super().action_post()


    def _reverse_moves(self, default_values_list=None, cancel=False):
        reversed_moves = super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)

        for new_move, origin in zip(reversed_moves, self):
            if origin.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
                if 'invoice_user_id' in new_move._fields:
                    new_move.invoice_user_id = origin.invoice_user_id.id
                if 'team_id' in new_move._fields:
                    new_move.team_id = origin.team_id.id
        return reversed_moves
    
    @api.depends('invoice_payments_widget')
    def _compute_total_amount_paid(self):
        for move in self:
            move.total_amount_paid = 0.0
            data = move.invoice_payments_widget
            if not data:
                continue

            try:
                payload = json.loads(data)
            except Exception:
                payload = False

            if not isinstance(payload, dict):
                continue

            content = payload.get('content') or []
            if not content:
                continue

            for item in content:
                amt = float(item.get('amount') or 0.0)
                move.total_amount_paid += amt

    
    def _compute_calendar_color_state(self):
        for move in self:
            if move.payment_state == 'paid':
                move.calendar_color_state = 'paid'
            else:
                move.calendar_color_state = 'not_paid'

    @api.depends('invoice_payments_widget')
    def _compute_payment_html(self):
        # contenedor que permite varias líneas
        wrap_css = (
            "white-space: normal;"
            "display: flex;"
            "flex-wrap: wrap;"
            "gap: 4px;"
            "align-items: center;"
        )
        # estilo de cada “cuadrito”
        box_css = (
            "display: inline-block;"
            "padding: 2px 6px;"
            "border: 1px solid #dcdcdc;"
            "border-radius: 6px;"
            "background: #f7f7f7;"
            "font-size: 12px;"
            "line-height: 18px;"
        )

        for move in self:
            move.payment_refs_html = False
            move.payment_amount_html = False
            move.payment_date_html = False
            move.total_amount_paid = 0.0

            data = move.invoice_payments_widget
            if not data:
                continue

            try:
                payload = json.loads(data)
            except Exception:
                payload = False

            if not isinstance(payload, dict):
                continue

            content = payload.get('content') or []
            if not content:
                continue

            # Ordenar por fecha (opcional)
            try:
                content = sorted(content, key=lambda d: d.get('date') or '')
            except Exception:
                pass

            # Acumuladores y anti-duplicado
            refs_tags, amts_tags, dates_tags = [], [], []
            seen = set()

            for item in content:
                ref = item.get('ref') or ''
                amt = float(item.get('amount') or 0.0)
                dstr = item.get('date') or ''
                dval = fields.Date.from_string(dstr) if dstr else False

                # clave para evitar duplicados del mismo pago
                key = item.get('account_payment_id') or item.get('payment_id') or f"{ref}|{dstr}|{amt}"
                if key in seen:
                    continue
                seen.add(key)

                # formateos
                amount_txt = format_amount(self.env, amt, move.currency_id or self.env.company.currency_id)
                date_txt = format_date(self.env, dval) if dval else ''
                move.total_amount_paid += amt
                # tags
                if ref:
                    refs_tags.append(f"<span style='{box_css}'>{ref}</span>")
                amts_tags.append(f"<span style='{box_css}'>{amount_txt}</span>")
                dates_tags.append(f"<span style='{box_css}'>{date_txt}</span>")

            if refs_tags:
                move.payment_refs_html = f"<div style='{wrap_css}'>{''.join(refs_tags)}</div>"
            if amts_tags:
                move.payment_amount_html = f"<div style='{wrap_css}'>{''.join(amts_tags)}</div>"
            if dates_tags:
                move.payment_date_html = f"<div style='{wrap_css}'>{''.join(dates_tags)}</div>"

    @api.depends('invoice_payments_widget')
    def _compute_payment_html_rp(self):
        wrap_css = "white-space:normal;display:flex;flex-wrap:wrap;gap:4px;align-items:center;"
        box_css  = "display:inline-block;padding:2px 6px;border:1px solid #dcdcdc;border-radius:6px;background:#f7f7f7;font-size:12px;line-height:18px;"

        for move in self:
            move.payment_refs_html_rp = False
            move.payment_amount_html_rp = False
            move.total_amount_paid = 0.0

            data = move.invoice_payments_widget
            try:
                payload = json.loads(data) if data else None
            except Exception:
                payload = None
            if not isinstance(payload, dict):
                continue

            content = payload.get('content') or []
            # (opcional) ordenar por fecha para consistencia visual
            try:
                content = sorted(content, key=lambda d: d.get('date') or '')
            except Exception:
                pass

            # Agrupar por ref y sumar montos
            sums_by_ref = OrderedDict()
            for item in content:
                ref = (item.get('ref') or '').strip()
                if not ref:
                    # si querés incluir los sin ref, podés hacer: ref = _("Sin ref.")
                    continue
                amt = float(item.get('amount') or 0.0)
                sums_by_ref[ref] = sums_by_ref.get(ref, 0.0) + amt

            if not sums_by_ref:
                continue

            # total cobrado (sobre lo agregado)
            move.total_amount_paid = sum(sums_by_ref.values())

            cur = move.currency_id or self.env.company.currency_id
            ref_tags = []
            amt_tags = []
            for ref, total in sums_by_ref.items():
                ref_tags.append(f"<span style='{box_css}'>{ref}</span>")
                amt_tags.append(f"<span style='{box_css}'>{format_amount(self.env, total, cur)}</span>")

            move.payment_refs_html_rp = f"<div style='{wrap_css}'>{''.join(ref_tags)}</div>"
            move.payment_amount_html_rp = f"<div style='{wrap_css}'>{''.join(amt_tags)}</div>"

    def _compute_amount_total_day(self):
        for record in self:
            if record.date_paid:
                #debe sumar las facturas de la misma fecha y sumar el amount_residual
                invoices = self.search([
                    ('date_paid', '=', record.date_paid),
                    ('move_type', '=', 'in_invoice'),
                    ('payment_state', '!=', 'paid'),
                    ('state', '=', 'posted'),
                ])
                record.amount_total_day = sum(inv.amount_residual for inv in invoices)
            else:
                record.amount_total_day = 0

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        for record in self:
            if record.journal_id:
                if record.journal_id.code == '00011':
                    invoice_incoterm_id = self.env['account.incoterms'].search([('code', '=', 'FAS')], limit=1).id
                    record.invoice_incoterm_id = invoice_incoterm_id
            
    @api.onchange('l10n_latam_document_type_id')
    def _onchange_document_type(self):
            for record in self:
                if record.l10n_latam_document_type_id.code == '201':

                    res_partner_bank = self.env['res.partner.bank'].search([
                    ('bank_name', '=', 'Banco Industrial S.A.'),
                    ('company_id', '=', record.company_id.id)
                    ], limit=1)

                    if res_partner_bank:
                        record.partner_bank_id = res_partner_bank.id
                    else:
                        raise UserError('No se encontró banco destinatario, asignar manualmente')
    
    # @api.onchange('partner_id')
    # def _onchange_update_taxed(self):
    #     for record in self:
    #         if record.invoice_line_ids:
    #             record.update_taxes()

    @api.onchange('partner_id')
    def _onchange_journal_gc(self):
        for record in self:
            if record.move_type == 'out_invoice' and record.partner_id:
                if record.partner_id.category_id and record.partner_id.category_id.filtered(lambda c: c.name == 'GC'):
                    journal_id = self.env['account.journal'].search([
                                ('code', '=', '00009'),
                                ('company_id', '=', record.company_id.id),
                                ('type', '=', 'sale')
                        ], limit=1)
                    if journal_id:
                        record.journal_id = journal_id
                    
    @api.model
    def cron_notify_date_paid(self):
        """Crea actividades para facturas cuya date_paid sea mañana,
        asignadas al usuario que creó la factura (create_uid)."""
        today = fields.Date.context_today(self)
        target = today + relativedelta(days=1)

        # Tipología de actividad "To Do"
        todo_type = self.env.ref("mail.mail_activity_data_todo")
        ir_model_id = self.env["ir.model"]._get_id("account.move")

        # Buscar facturas relevantes (ajustá move_type/state a tu necesidad)
        moves = self.search([
            ("date_paid", "=", target),
            ("move_type", "=", "in_invoice"),
            ("state", "in", ["draft", "posted"]),
            ("state_paid", "!=", "paid"),
        ])

        group = self.env.ref("account_enhancement.group_recordatorio_pago", raise_if_not_found=False)
        if not group or not group.users:
            return  # sin usuarios, no hay a quién notificar

        for move in moves:
            for user in group.users:
                # Evitar duplicados: ¿ya existe una actividad igual?
                existing = self.env["mail.activity"].search_count([
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", move.id),
                    ("activity_type_id", "=", todo_type.id),
                    ("user_id", "=", user.id),
                    ("summary", "=", "Recordatorio: Debe realizar el pago de la factura falta 1 día"),
                ])

                if existing:
                    continue

                # Crear actividad
                self.env["mail.activity"].create({
                    "activity_type_id": todo_type.id,
                    "res_model_id": ir_model_id,
                    "res_id": move.id,
                    "user_id": user.id,
                    "summary": _("Recordatorio: Debe realizar el pago de la factura falta 1 día"),
                    "note": _("La factura %s tiene fecha de pago %s.")
                            % (move.name or move.ref or move.id, move.date_paid),
                    "date_deadline": target,
                })



class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

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
    
class WmsCode(models.Model):
    _name = "wms.code"
    _description = "Código WMS"

    name = fields.Char("Código", required=True)


class AccountPaymentInherit(models.TransientModel):
    _inherit = 'account.payment.mass.transfer'


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get('active_model') != 'account.payment':
            raise UserError(_("The register payment wizard should only be called on account.payment records."))
        payments = self.env['account.payment'].browse(self._context.get('active_ids', []))
        checks = payments.filtered(lambda x: x.payment_method_line_id.code == 'new_third_party_checks')
        if not all(check.state == 'posted' for check in checks):
            raise UserError(_("All the selected checks must be posted"))
        self.filtered(lambda x: x.payment_method_line_id.code in ['in_third_party_checks', 'out_third_party_checks'])
        if not checks[0].l10n_latam_check_current_journal_id.inbound_payment_method_line_ids.filtered(
                lambda x: x.code == 'in_third_party_checks'):
            raise UserError(_("Checks must be on a third party checks journal to be transfered by this wizard"))
        res['journal_id'] = checks[0].l10n_latam_check_current_journal_id.id
        return res
    

class AccountMoveReversalInherit(models.TransientModel):
    _inherit = 'account.move.reversal'


    def _prepare_default_reversal(self, move):
        vals = super()._prepare_default_reversal(move)
        if self.refund_method in ['modify', 'cancel']:
            vals['auto_post'] = 'no' 
        return vals

    def reverse_moves(self):
        action = super().reverse_moves()
        new_moves = self.new_move_ids

        today = fields.Date.context_today(self)
        credit_notes = self.env['account.move'].search([
            ('reversed_entry_id', 'in', self.move_ids.ids),
            ('move_type', '=', 'out_refund')], limit=1)
        
        invoice_date = None
        for move in self.move_ids:
            invoice_date = move.invoice_date

        # rango de fecha cambiar a periodo ejemplo solo se puede quitar las perceppcion_iibb si estamos en el mismo mes
        periodo_actual = today.month
        if invoice_date:
            periodo_factura = invoice_date.month

        if credit_notes and self.refund_method == 'modify':
            if periodo_actual != periodo_factura:
                self._delete_impuestos_perceppcion_iibb(credit_notes)
                credit_notes.update_taxes()
                credit_notes._compute_amount()
                credit_notes.action_post()
                # Conciliación entre factura original y NC (para que cambie el payment_state)
                for origin in self.move_ids:
                    cns = credit_notes.filtered(lambda m: m.reversed_entry_id == origin and m.state == 'posted')
                    if not cns:
                        continue
                    receiv_pay_lines = (origin.line_ids + cns.line_ids).filtered(
                        lambda l: l.account_id.internal_type in ('receivable', 'payable') and not l.reconciled
                    )
                    if receiv_pay_lines:
                        if hasattr(receiv_pay_lines, 'auto_reconcile_lines'):
                            receiv_pay_lines.auto_reconcile_lines()
                        else:
                            receiv_pay_lines.reconcile()
                    origin.write({'payment_state': 'reversed'})
        for new_move in new_moves:
            invoice_date = new_move.invoice_date if new_move else None
            if self.refund_method == 'refund':
                if not new_move:
                    return action
                self._delete_impuestos_perceppcion_iibb(new_move)
            else:
                if periodo_actual != periodo_factura:
                    self._delete_impuestos_perceppcion_iibb(new_move)
            new_move.update_taxes()
        return action
    
    def _delete_impuestos_perceppcion_iibb(self, move):
        tax_name = 'percepción iibb'
        for line in move.invoice_line_ids:
            line_tax_ids = line.tax_ids.filtered(lambda t: tax_name not in (t.name or '').lower())
            if line_tax_ids:
                line.write({'tax_ids': [(6, 0, line_tax_ids.ids)]})

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_resumen_composicion(self):
        """Abrir facturas del cliente (y contactos hijos) en vista tree personalizada."""
        self.ensure_one()
        action = self.env.ref('account_enhancement.action_partner_invoices_tree').read()[0]
        # facturas cliente + NC cliente, solo publicadas; incluye partner y sus hijos
        action['domain'] = [
            ('move_type', 'in', ['out_invoice']),
            ('state', '=', 'posted'),
            ('partner_id', 'child_of', self.commercial_partner_id.id),
        ]
        # orden por fecha de factura (reciente primero)
        action['context'] = {
            'search_default_group_by_partner': 0,
            'search_default_open': 0,
            'default_move_type': 'out_invoice',
        }
        return action


#SOLO DEBERIA ESTAR ACTIVO PARA EL SERVIDOR DE TEST PARA HACER PRUEBAS CON AFIP
#class AccountJournalInherit(models.Model):
#    _inherit = 'account.journal'

#    @api.depends("l10n_ar_afip_pos_system")
#    def _compute_afip_ws(self):
#        """Depending on AFIP POS System selected set the proper AFIP WS"""
#        type_mapping = self._get_type_mapping()
#        for rec in self:
#            rec.afip_ws = False


class AccountMovelLineInherit(models.Model):
    _inherit = 'account.move.line'

    lot_id = fields.Many2one('stock.production.lot', string='Nro Lote')