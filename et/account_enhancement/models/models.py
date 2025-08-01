# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import AccessError, UserError, ValidationError
import logging
from datetime import date
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

    # @api.model
    # def create(self, vals):
    #     if vals.get('move_type') == 'out_refund' and vals.get('invoice_line_ids'):
    #         # Buscar una sola vez los taxes de percepción
    #         percepcion_tax_ids = self.env['account.tax'].search([('name', 'ilike', 'perc')]).ids

    #         for line in vals['invoice_line_ids']:
    #             if isinstance(line, (list, tuple)) and len(line) > 2:
    #                 line_vals = line[2]
    #                 tax_ids_cmd = line_vals.get('tax_ids', [])
    #                 if tax_ids_cmd and tax_ids_cmd[0][0] == 6:
    #                     ids = tax_ids_cmd[0][2]
    #                     filtered_ids = [tid for tid in ids if tid not in percepcion_tax_ids]
    #                     line_vals['tax_ids'] = [(6, 0, filtered_ids)]
    #     return super().create(vals)


    # @api.onchange('invoice_line_ids')
    # def _onchange_invoice_line_ids_remove_perceptions(self):
    #     if self.move_type == 'out_refund':
    #         for line in self.invoice_line_ids:
    #             line.tax_ids = line.tax_ids.filtered(lambda t: not t.name.lower().startswith('perc'))
    
    # def _reverse_moves(self, default_values_list=None, cancel=False):
    #     reversed_moves = super()._reverse_moves(default_values_list, cancel=cancel)
    #     # Sacar percepciones de las líneas de la NC antes de postear
    #     for move in reversed_moves:
    #         if move.move_type == 'out_refund':
    #             for line in move.invoice_line_ids:
    #                 percep_taxes = line.tax_ids.filtered(lambda t: 'perc' in t.name.lower())
    #                 if percep_taxes:
    #                     # IMPORTANTE: Solo si NO está posted!
    #                     if move.state == 'draft':
    #                         line.tax_ids = line.tax_ids - percep_taxes
    #         move.update_taxes()
    #     return reversed_moves

    
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


    @api.onchange('partner_id')
    def _onchange_journal_gc(self):
        journal_id = self.env['account.journal'].search([
            ('l10n_ar_afip_pos_number', '=', 9),
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'sale')
        ], limit=1) 

        for record in self:
            if record.partner_id:
                category_ids = record.partner_id.category_id.mapped('id')
                
                if 75 in category_ids and journal_id:
                    record.journal_id = journal_id



class AccountPaymentInherit(models.Model):
    _inherit = 'account.payment'

    issue_date = fields.Date(string='Fecha de Emisión')
    hide_issue_date = fields.Boolean(default=True)
    no_diferido = fields.Boolean('No diferido', default=False)
    no_a_la_orden = fields.Boolean('No a la Orden', default=False)
    rejected = fields.Boolean('Cheque Rechazado', default=False)
    check_state = fields.Char(
        string="Estado del Cheque",
        compute='_compute_check_state',
        store=True,
        readonly=True
    )
    journal_code = fields.Char(related='journal_id.code', store=True)
    #hereadado
    l10n_ar_amount_company_currency_signed = fields.Monetary(
        compute='_compute_l10n_ar_amount_company_currency_signed',
        currency_field='company_currency_id',
        store=True,  # <<-- esto lo hace almacenado, ahora es ordenable y filtrable
        string='Importe en moneda compañía',  # Cambia el nombre aquí si quieres
    )


    @api.depends('l10n_latam_check_current_journal_id')
    def _compute_check_state(self):
        for rec in self:
            if rec.rejected:
                rec.check_state = 'Rechazado'
            elif rec.l10n_latam_check_current_journal_id:
                journal_code = rec.l10n_latam_check_current_journal_id.code
                journal_type = rec.l10n_latam_check_current_journal_id.type
                if journal_code in ('CSH3', 'CSH5', 'ECHEQ'):
                    rec.check_state = 'En Cartera'
                elif journal_type == 'bank':
                    rec.check_state = 'Depositado'
            else:
                rec.check_state = 'Entregado'

    def action_reject_check(self):
        for rec in self:
            rec.rejected = True
            rec._compute_check_state()

    def action_undo_reject_check(self):
        for rec in self:
            rec.rejected = False
            rec._compute_check_state()

    @api.onchange('no_diferido')
    def _onchange_no_diferido(self):
        if self.no_diferido:
            self.issue_date = False

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


    executive_id = fields.Many2one(
        'res.users',
        string="Ejecutivo de Cuenta",
        related='partner_id.executive_id',
        store=True,
        readonly=True
    )

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
            check_numbers = {}

            for payment_line in rec.payment_ids:
                if payment_line.check_number:
                    check_numbers[payment_line.id] = payment_line.check_number


            _logger.info(check_numbers.items)

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
                if payment_line.id in check_numbers:
                    payment_line.check_number = check_numbers[payment_line.id]

            rec.state = 'posted'

            if rec.receiptbook_id.mail_template_id:
                rec.message_post_with_template(rec.receiptbook_id.mail_template_id.id)
        return True
    

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


    # def _prepare_default_reversal(self, move):
    #     vals = super()._prepare_default_reversal(move)
    #     # Forzamos borrador sí o sí
    #     vals['auto_post'] = False
    #     vals['state'] = 'draft'
    #     # Opcional: filtrar percepciones aquí también, como antes
    #     invoice_lines = []
    #     if move.is_invoice(include_receipts=True) and move.move_type == 'out_refund':
    #         for line in move.invoice_line_ids:
    #             new_line_vals = line.copy_data()[0]
    #             tax_ids = new_line_vals.get('tax_ids', [])
    #             if tax_ids:
    #                 percep_ids = self.env['account.tax'].search([('name', 'ilike', 'perc')]).ids
    #                 if tax_ids and isinstance(tax_ids[0], (list, tuple)):
    #                     tid_list = tax_ids[0][2]
    #                 else:
    #                     tid_list = tax_ids
    #                 new_line_vals['tax_ids'] = [(6, 0, [tid for tid in tid_list if tid not in percep_ids])]
    #             invoice_lines.append((0, 0, new_line_vals))
    #         vals['invoice_line_ids'] = invoice_lines
    #     return vals

    # def reverse_moves(self):
    #     res = super().reverse_moves()
    #     for move in self.new_move_ids:
    #         # Limpiá percepciones si quedara alguna
    #         for line in move.invoice_line_ids:
    #             line.tax_ids = line.tax_ids.filtered(lambda t: not t.name.lower().startswith('perc'))
    #         # Ahora publicá (posteá) la NC, así se va a AFIP
    #         move.action_post()
    #     return res
