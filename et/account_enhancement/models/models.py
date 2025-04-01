# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    # @api.onchange('partner_id')
    # def _onchange_journal_gc(self):
    #     for record in self:
    #         tag_id = record.partner_id.category_id
    #         journal_id = self.env['account.journal'].search([('l10n_ar_afio_pos_number', '=', 9), ('company_id', '=', record.company_id)])
    #         if tag_id == 78 and journal_id:
    #             record.journal_id = journal_id



class AccountPaymentInherit(models.Model):
    _inherit = 'account.payment'

    issue_date = fields.Date(string='Fecha de Emisión')
    hide_issue_date = fields.Boolean(default=True)

    @api.depends('journal_id', 'payment_method_code')
    def _compute_check_number(self):
        for pay in self:
            if pay.journal_id.check_manual_sequencing and pay.payment_method_code == 'check_printing':
                sequence = pay.journal_id.check_sequence_id
                pay.check_number = sequence.get_next_char(sequence.number_next_actual)
    
    @api.onchange('journal_id')
    def _onchange_hide_issue_date(self):
        for record in self:
            if record.journal_id.default_account_id.name == 'Cheques de terceros':
                record.hide_issue_date = False
            else:
                record.hide_issue_date = True



class AccountPaymentGroupInherit(models.Model):
    _inherit = 'account.payment.group'


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
            check_numbers = {}

            for payment_line in rec.payment_ids:
                check_numbers[payment_line.id] = payment_line.check_number
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
            # por ahora solo lo usamos en _get_last_sequence_domain para saber si viene de una transferencia (sin
            # documen type) o es de un grupo de pagos. Pero mas alla de eso no tiene un gran uso, viene un poco legacy
            # y ya está configurado en los receibooks
            rec.payment_ids.l10n_latam_document_type_id = rec.document_type_id.id

            if not rec.payment_ids:
                raise ValidationError(_(
                    'You can not confirm a payment group without payment lines!'))
            # si todos los pagos hijos estan posteados es probable que venga de un pago creado en otro lugar
            # (expenses por ejemplo), en ese caso salteamos la dobule validation
            if (rec.payment_subtype == 'double_validation' and rec.payment_difference and not created_automatically):
                raise ValidationError(_('To Pay Amount and Payment Amount must be equal!'))

            # if the partner of the payment is different of ht payment group we change it.
            rec.payment_ids.filtered(lambda p: p.partner_id != rec.partner_id.commercial_partner_id).write(
                {'partner_id': rec.partner_id.commercial_partner_id.id})

            
            
            # no volvemos a postear lo que estaba posteado
            if not created_automatically:
                rec.payment_ids.filtered(lambda x: x.state == 'draft').action_post()
            # escribimos despues del post para que odoo no renumere el payment
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
                if payment_line.id in check_numbers:
                    payment_line.check_number = check_numbers[payment_line.id]

            rec.state = 'posted'

            if rec.receiptbook_id.mail_template_id:
                rec.message_post_with_template(rec.receiptbook_id.mail_template_id.id)
        return True
