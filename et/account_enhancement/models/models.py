# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import AccessError, UserError, ValidationError
import logging
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

    def get_pickings(self):
        wms_codes = ["D12024", "P2160", "P2159", "P2169", "D12000", "D12067", "D12001", "P2152", "P2241", "P2242", "P2243", "P2237", "P2239", "D12075", "P1996", "D11993", "D11994", "P2235", "P329", "P330", "P331", "P332", "P333", "P334", "P335","P336", "D10561", "P732", "P733", "P744", "P2211", "D12056", "D11143", "D11144", "D11142", "D11145", "D11146", "P905", "D11256", "P1222", "P1233", "P1234", "P1371", "P1515", "P1566", "D11483", "D11484", "P1684", "P1685","P1688", "P1689", "P1690", "P1691", "P1692", "P1693", "P1694", "P1657", "P1656", "D11527", "D11529", "D11509", "D11583", "P1699", "P1700", "P1701", "P1702", "P1705", "P1706", "P1709", "P1719", "D11693", "P1813", "P1814","D11876", "D11645", "D11644", "D11646", "P1768", "D11705", "D11704", "D11706", "P1891", "P1902", "P1903", "P1904", "P1905", "P1906", "P1888", "P1889", "P1890", "P1922", "D11751", "D11752", "D11681", "D11680", "P1948","P1949", "D11803", "D11802", "D11857", "D11858", "D11907", "D11908", "P2045", "D11894", "P2018", "P2031", "P2053", "P2054", "P2059", "P2060", "P1978", "P2015", "D11868", "P2005", "P1982", "P2013", "D11875", "D11874","P2052", "D11970", "D11927", "P2075", "P2074", "P2076", "D11951", "P2091", "P2092", "D11926", "D11935", "D11941", "P2119", "P2118", "P2122", "D11911", "D11913", "D11932", "D11933", "D12006", "D12039", "D11984","P2254", "D11991", "D11992", "P2153", "D12021", "D12022", "D12020", "D11980", "D11979", "D11978", "D11997", "P2252", "D11998", "P2158", "P2157", "D12007", "P2164", "D12014", "D12015", "D12027", "D12033", "P2140","P2165", "P2166", "P2167", "P2233", "P2182", "D12041", "P2207", "P2231", "D12062", "P2234", "D12066", "P2216", "P2238", "P2236", "D12057", "P2212", "P2208", "P2291", "D12099", "D12104", "D8892", "D8894", "D8896", "D8898", "D8900", "D8902", "D8893", "D8895", "D8897", "D8899", "D8901", "D8903"]

        invoices = self.env['account.move'].search([('wms_code', 'in', wms_codes)])
        
        result = []


        for i in invoices:
            result.append(f"{i.name},{i.wms_code},{i.invoice_date},{i.amount_total_signed}")

        result2 = '\n'.join(result)

        raise UserError(result2)


    def corregir_facturas(self):
        invoices_names1 = set()
        invoices_names1_nonc = set()
        invoices_names2 = set()
        invoices_names3 = set()
        invoices_names4 = set()
        detalle_ncs = set()

        for record in self:
            sale_order = False
            if record.invoice_origin:
                sale_order = self.env['sale.order'].search([('name', '=', record.invoice_origin)], limit=1)
            if not sale_order:
                continue

            order_prices = {
                line.product_id.id: line.price_unit
                for line in sale_order.order_line
            }

            for line in record.invoice_line_ids:
                if line.product_id and line.product_id.id in order_prices:
                    sale_price = order_prices[line.product_id.id]
                    if line.price_unit != sale_price:
                        if sale_order.condicion_m2m.name == 'TIPO 1':                            
                            nc = self.env['account.move'].search([
                                ('move_type', '=', 'out_refund'),
                                ('reversed_entry_id.name', '=', record.name)
                            ], limit=1)
                                                      
                            if nc:
                                invoices_names1.add(f"{record.name} - {nc.name}")
                            else:                                
                                invoices_names1_nonc.add(f"{record.name}")

                        elif sale_order.condicion_m2m.name == 'TIPO 2':
                            invoices_names2.add(record.name)
                        elif sale_order.condicion_m2m.name == 'TIPO 3':
                            invoices_names3.add(record.name)
                        elif sale_order.condicion_m2m.name == 'TIPO 4':
                            invoices_names4.add(record.name)

        invoices_t1 = '\n'.join(invoices_names1_nonc)
        invoices_t2 = ', '.join(invoices_names2)
        invoices_t3 = ', '.join(invoices_names3)
        invoices_t4 = ', '.join(invoices_names4)

        ncs_t1 = '\n'.join(invoices_names1)

        raise UserError(
            f'Facturas TIPO 1 SIN NC: {invoices_t1} \n\n'
            f'Facturas TIPO 1 CON NC:\n{ncs_t1}\n\n'
            f'Facturas TIPO 2: {invoices_t2} \n'
            f'Facturas TIPO 3: {invoices_t3} \n'
            f'Facturas TIPO 4: {invoices_t4}'
        )



    def corregir_precios(self):
        for record in self:
            if record.state != 'draft':
                raise UserError("Solo se pueden corregir precios en facturas en borrador.")

            sale_order = False
            if record.invoice_origin:
                sale_order = self.env['sale.order'].search([('name', '=', record.invoice_origin)], limit=1)
            if not sale_order:
                continue

            tipo = sale_order.condicion_m2m
            tipo_nombre = tipo and tipo.name or ''
            if tipo_nombre.upper().strip() != 'TIPO 3':
                continue

            order_prices = {
                line.product_id.id: line.price_unit
                for line in sale_order.order_line
            }

            lines_to_update = []
            for inv_line in record.invoice_line_ids:
                if inv_line.product_id and inv_line.product_id.id in order_prices:
                    sale_price = order_prices[inv_line.product_id.id]
                    if inv_line.price_unit != sale_price:
                        lines_to_update.append((1, inv_line.id, {'price_unit': sale_price}))

            if lines_to_update:
                record.write({'invoice_line_ids': lines_to_update})
                if hasattr(record, '_recompute_dynamic_lines'):
                    record._recompute_dynamic_lines()
                record._compute_amount()
                record.write({})

    
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