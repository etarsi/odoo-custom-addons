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

class AccountPaymentInherit(models.Model):
    _inherit = "account.payment"

    issue_date = fields.Date(string='Fecha de Emisión')
    hide_issue_date = fields.Boolean(default=True)
    no_diferido = fields.Boolean('No diferido', default=False)
    no_a_la_orden = fields.Boolean('No a la Orden', default=False)
    rejected = fields.Boolean('Cheque Rechazado', default=False)
    check_state = fields.Char(
        string="Estado del Cheque",
        compute='_compute_check_state',
        store=True,
    )
    journal_code = fields.Char(related='journal_id.code', store=True)
    #hereadado
    l10n_ar_amount_company_currency_signed = fields.Monetary(
        compute='_compute_l10n_ar_amount_company_currency_signed',
        currency_field='company_currency_id',
        store=True,  # <<-- esto lo hace almacenado, ahora es ordenable y filtrable
        string='Importe en moneda compañía',  # Cambia el nombre aquí si quieres
    )
    is_effectiveness_text = fields.Boolean(default=False)
    check_effectiveness_text = fields.Text(compute="_compute_check_effectiveness", store=False)
    index = fields.Integer(string='#')
    archived = fields.Boolean(string='Archivado', related='payment_group_id.archived', store=True)
    period_cut_locked = fields.Boolean(string="Período de Corte Bloqueado", related='payment_group_id.period_cut_locked', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("period_cut_locked"):
                raise ValidationError(_("No se puede crear un pago con 'Período de Corte Bloqueado' activo."))
        return super().create(vals_list)

    def write(self, vals):
        for payment in self:
            if vals.get("period_cut_locked") or payment.period_cut_locked:
                raise ValidationError(_("No se puede modificar un pago con 'Período de Corte Bloqueado' activo."))
            res = super().write(vals)
            payment._constrains_check_number_length()
        return res

    def unlink(self):
        for payment in self:
            if payment.period_cut_locked:
                raise ValidationError(_("No se puede eliminar un pago con 'Período de Corte Bloqueado' activo."))
            if payment.payment_group_id:                
                if payment.payment_group_id.partner_type == 'supplier':
                    if payment.l10n_latam_check_current_journal_id:
                        journal_code = payment.l10n_latam_check_current_journal_id.code
                        if journal_code in ('CSH3', 'CSH5', 'ECHEQ'):
                            if payment.l10n_latam_check_id:                       
                                payment.l10n_latam_check_id.check_state = 'En Cartera'        
        return super().unlink()    

    @api.constrains('check_number', 'journal_id')
    def _constrains_check_number(self):
        return

    @api.depends('state')
    def _compute_state(self):
        for record in self:
            if record.payment_group_id:
                if record.payment_type == 'outbound':
                    if record.state == 'draft':
                        record.check_state = 'Pendiente'

                        if record.journal_id.code in ('CSH3', 'CSH5', 'ECHEQ'):
                            if record.l10n_latam_check_id:                             
                                record.check_number = record.l10n_latam_check_id.check_number or ''
                                record.l10n_latam_check_id.check_state = 'Pendiente'

                    elif record.state == 'posted':
                        record.check_state = 'Entregado'

    @api.onchange('l10n_latam_check_issuer_vat', 'payment_method_line_id', 'journal_id')
    def _compute_check_effectiveness(self):
        success_states = {'Entregado'}
        rejected_states = {'Rechazado'}
        for rec in self:
            rec.is_effectiveness_text = False
            rec.check_effectiveness_text = False
            if not (rec.l10n_latam_check_issuer_vat and rec.journal_id):
                continue
            if rec.journal_id.code not in ('CSH3', 'ECHEQ', 'CSH5'):
                continue
            payments = self.env['account.payment'].search([('l10n_latam_check_issuer_vat', '=', rec.l10n_latam_check_issuer_vat),
                                                            ('state', '=', 'posted')])
            if payments:
                succ_amount = 0
                rej_amount = 0
                for p in payments:
                    st = p.check_state
                    amt = p.amount or 0.0
                    
                    if st in success_states:
                        succ_amount += amt
                    elif st in rejected_states:
                        rej_amount += amt
                base = succ_amount + rej_amount
                if base == 0:
                    continue
                pct = int(round(100.0 * succ_amount / float(base)))
                rec.check_effectiveness_text = _("%(pct)s%% Cheques Aprobados") % {'pct': pct}
                rec.is_effectiveness_text = True

    @api.depends('l10n_latam_check_current_journal_id')
    def _compute_check_state(self):
        for rec in self:
            if rec.payment_type == 'inbound':
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

            elif rec.payment_type == 'outbound':
                if rec.state == 'draft':
                    rec.check_state = 'Pendiente'

                    if rec.journal_id.code in ('CSH3', 'CSH5', 'ECHEQ'):
                        if rec.l10n_latam_check_id:
                            # rec.check_number = rec.l10n_latam_check_id.check_number or ''

                            rec.l10n_latam_check_id.check_state = 'Pendiente'

 
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
                
    #VALIDAR check_number SEA MINIMO Y MAXIMO DE 8 DIGITOS
    @api.onchange('check_number', 'journal_id')
    def _constrains_check_number_length(self):
        for record in self:
            if record.check_number and record.journal_id.code in ('CSH3', 'CSH4', 'ECHEQ'):
                if len(record.check_number) > 8:
                    raise ValidationError(_('El Número de cheque debe tener 8 dígitos como máximo.'))

