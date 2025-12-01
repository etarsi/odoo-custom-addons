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


class AccountPaymentGroupInherit(models.Model):
    _inherit = 'account.payment.group'

    executive_id = fields.Many2one(
        'res.users',
        string="Ejecutivo de Cuenta",
        related='partner_id.executive_id',
        store=True,
        readonly=True
    )
    paid_date_venc_html = fields.Html(
        compute='_compute_paid_date_venc_html',
        string="Vencimientos vs fecha de pago",
        sanitize=False,
    )
    is_paid_date_venc_text = fields.Boolean(default=False, copy=False)
    paid_date_venc_text = fields.Text(default='⚠️ EL PAGO A REGISTRAR ESTA FUERA DE FECHA ⚠️')          
    active = fields.Boolean(string='Activo', default=True)


    
    #### ONCHANGE #####
    @api.onchange('payment_date', 'to_pay_move_line_ids', 'to_pay_move_line_ids.date_maturity', 'to_pay_move_line_ids.move_id')
    def _compute_paid_date_venc_html(self):
        for rec in self:
            rec.paid_date_venc_html = False
            if not rec.payment_date or not rec.to_pay_move_line_ids:
                continue

            overdue_items = []   # pago > vencimiento
            same_day_items = []  # pago == vencimiento

            for l in rec.to_pay_move_line_ids.filtered(lambda x: x.date_maturity):
                due = l.date_maturity
                delay = (rec.payment_date - due).days
                inv = l.move_id.display_name or l.move_id.name or (l.move_id.ref or str(l.move_id.id))

                if delay > 0:
                    overdue_items.append(
                        "%s — vence: %s — atraso: %s día(s)" %
                        (inv, format_date(self.env, due), delay)
                    )
                elif delay == 0:
                    same_day_items.append(
                        "%s — vence hoy (%s)" %
                        (inv, format_date(self.env, due))
                    )

            if overdue_items or same_day_items:
                rec.is_paid_date_venc_text = True
                parts = []
                title = _("La fecha de pago (%s)") % format_date(self.env, rec.payment_date)
                if overdue_items:
                    parts.append("<p><strong>%s %s</strong></p><ul>%s</ul>" % (
                        title, _("es mayor a la fecha de vencimiento en:"),
                        "".join("<li>%s</li>" % i for i in overdue_items)
                    ))
                if same_day_items:
                    parts.append("<p><strong>%s</strong></p><ul>%s</ul>" % (
                        _("Vencen el mismo día:"),
                        "".join("<li>%s</li>" % i for i in same_day_items)
                    ))
                css = 'alert-danger' if overdue_items else 'alert-info'
                rec.paid_date_venc_html = "<div class='alert %s'>%s</div>" % (css, "".join(parts))

    def set_payments_date(self):
        for record in self:
            for payment_line in record.payment_ids:
                payment_line.date = record.payment_date

    def post(self):
        """ Post payment group. If payment is created automatically when creating a payment (for eg. from website
        or expenses), then:
        1. do not post payments (posted by super method)
        2. do not reconcile (reconciled by super)
        3. do not check double validation
        TODO: may be we can improve code and actually do what we want for payments from payment groups"""
        

        created_automatically = self._context.get('created_automatically')
        posted_payment_groups = self.filtered(lambda x: x.state == 'posted')
        if posted_payment_groups:
            raise ValidationError(_(
                "You can't post and already posted payment group. Payment group ids: %s") % posted_payment_groups.ids)
        for rec in self:
            if not rec.document_number:
                if rec.receiptbook_id and not rec.receiptbook_id.sequence_id:
                    raise ValidationError(_(
                        'Error!. Please define sequence on the receiptbook'
                        ' related documents to this payment or set the '
                        'document number.'))
                if rec.receiptbook_id.sequence_id:
                    rec.document_number = (
                        rec.receiptbook_id.with_context(
                            ir_sequence_date=rec.payment_date
                        ).sequence_id.next_by_id())
            rec.payment_ids.l10n_latam_document_type_id = rec.document_type_id.id

            if not rec.payment_ids:
                raise ValidationError(_(
                    'You can not confirm a payment group without payment lines!'))
            if (rec.payment_subtype == 'double_validation' and rec.payment_difference and not created_automatically):
                raise ValidationError(_('To Pay Amount and Payment Amount must be equal!'))

            rec.payment_ids.filtered(lambda p: p.partner_id != rec.partner_id.commercial_partner_id).write(
                {'partner_id': rec.partner_id.commercial_partner_id.id})

            
            
            if not created_automatically:
                rec.payment_ids.filtered(lambda x: x.state == 'draft').action_post()
            rec.payment_ids.name = rec.name

            if not rec.receiptbook_id and not rec.name:
                rec.name = any(
                    rec.payment_ids.mapped('name')) and ', '.join(
                    rec.payment_ids.mapped('name')) or False

            if not created_automatically:
                counterpart_aml = rec.payment_ids.mapped('line_ids').filtered(
                    lambda r: not r.reconciled and r.account_id.internal_type in ('payable', 'receivable'))
                if counterpart_aml and rec.to_pay_move_line_ids:
                    (counterpart_aml + (rec.to_pay_move_line_ids)).reconcile()

            for payment_line in rec.payment_ids:

                if payment_line.payment_type == 'outbound':
                    payment_line.check_state = "Entregado"
                    if payment_line.l10n_latam_check_id:
                        payment_line.check_number = payment_line.l10n_latam_check_id.check_number
                
                if payment_line.payment_type == 'inbound':
                    payment_line.check_state = "En Cartera"


        

            rec.state = 'posted'

            if rec.receiptbook_id.mail_template_id:
                rec.message_post_with_template(rec.receiptbook_id.mail_template_id.id)


        return True
    

    @api.onchange('payment_ids')
    def _onchange_payment_ids(self):
        for record in self:
            payment_index = 0
            if record.payment_ids:
                for payment in record.payment_ids:
                    payment_index += 1
                    payment.index = payment_index
                    if payment.journal_id.code in ('CSH3', 'CSH5', 'ECHEQ'):
                        if payment.l10n_latam_check_id:
                            payment.check_number = payment.l10n_latam_check_id.check_number or ''

    
    def action_draft(self):
        for record in self:
            if record.partner_type == 'supplier':
                if record.payment_ids:
                    for payment in record.payment_ids:
                        payment.check_state = 'Pendiente'
            if record.payment_ids:
                for payment in record.payment_ids:
                    if payment.check_state == 'Entregado':
                        raise ValidationError(_(
                            "No se puede volver a borrador un grupo de pagos, que contiene pagos con cheques entregados."
                        ))
            recs = super().action_draft()

            return recs
        

    def action_resecuence(self):
        for record in self:
            if record.payment_ids:
                payments = record.payment_ids.sorted(lambda p: (p.l10n_ar_amount_company_currency_signed or 0.0, p.id))
                for indx, payment in enumerate(payments, start=1):
                    payment.index = indx
                    
    def un_link(self):
        for record in self:
            to_archive = record.filtered(lambda r: r.state in ('draft', 'cancel'))
            others = record - to_archive
            if others:
                raise UserError(_(
                    "Solo se pueden suprimir grupos de pago en estado Borrador "
                    "o Cancelado.\nEstados no permitidos: %s"
                ) % ', '.join(sorted(set(others.mapped('state')))))
            if to_archive:
                to_archive.write({'active': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Listo',
                'message': 'Se Eliminaron los grupos de pago seleccionados.',
                'type': 'success',
                'sticky': False,
            }
        }

    #### DEPENDS #####
    @api.depends('partner_id', 'partner_type', 'company_id')
    def _compute_to_pay_move_lines(self):
        for record in self:
            return