# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class AccountMoveRoundingInvoiceWizard(models.TransientModel):
    _name = 'account.move.rounding.invoice.wizard'
    _description = 'Wizard - Facturas de redondeo desde líneas contables'

    line_ids = fields.One2many(
        'account.move.rounding.invoice.wizard.line',
        'wizard_id',
        string='Líneas'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        lines = self._get_selected_source_lines()
        _logger.info('Líneas seleccionadas para redondeo: %s', lines.ids)

        if not lines:
            raise UserError(_(
                'No hay líneas válidas seleccionadas.\n\n'
                'Seleccioná líneas contables pendientes en cuenta a cobrar.'
            ))

        groups = self._group_selected_lines(lines)
        _logger.info('Grupos de líneas seleccionadas: %s', groups)

        if not groups:
            raise UserError(_(
                'No se encontraron líneas pendientes en cuenta a cobrar con residual negativo.'
            ))

        line_commands = []
        for data in groups.values():
            partner = data['partner']
            company = data['company']
            account = data['account']
            currency = data['currency']
            move_ids = data['move_ids']
            move_line_ids = data['move_line_ids']
            journal = data['journal']
            product = data['product']
            amount_total = self._get_group_amount(move_line_ids, currency, company)

            if amount_total <= 0:
                continue

            line_commands.append((0, 0, {
                'partner_id': partner.id,
                'company_id': company.id,
                'account_id': account.id,
                'currency_id': currency.id,
                'move_ids': [(6, 0, move_ids.ids)],
                'move_line_ids': [(6, 0, move_line_ids.ids)],
                'move_count': len(move_ids),
                'amount_total': amount_total,
                'move_names': self._get_move_names(move_ids),
                'journal_id': journal.id,
                'product_id': product.id,
            }))

        if not line_commands:
            raise UserError(_('No hay agrupaciones válidas para procesar.'))

        res['line_ids'] = line_commands
        return res

    def _get_selected_source_lines(self):
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model')

        if active_model != 'account.move.line':
            raise UserError(_('Este asistente solo puede ejecutarse desde líneas contables.'))

        if not active_ids:
            return self.env['account.move.line']

        lines = self.env['account.move.line'].browse(active_ids).exists()

        not_posted = lines.filtered(lambda l: l.move_id.state != 'posted')
        if not_posted:
            raise UserError(_('Todas las líneas seleccionadas deben pertenecer a movimientos publicados.'))

        return lines.filtered(self._is_candidate_line)

    def _is_candidate_line(self, line):
        if not line.partner_id:
            return False

        if line.currency_id and line.currency_id != line.company_currency_id:
            residual = line.amount_residual_currency
        else:
            residual = line.amount_residual

        # pensado para saldos acreedores del cliente
        return residual < -0.00001

    def _group_selected_lines(self, lines):
        groups = {}

        for line in lines:
            partner = line.partner_id
            company = line.company_id
            currency = line.currency_id or line.company_currency_id
            move = line.move_id
            account = self.env['account.account'].search([
                        ('company_id', '=', company.id),
                        ('code', '=', '4.2.1.01.030'),
                    ], limit=1)
            key = (partner.id, company.id, currency.id)
            journal = self.env['account.journal'].search([
                        ('company_id', '=', company.id),
                        ('name', 'ilike', 'Reclasificacion'),
                        ('type', '=', 'sale'),
                    ], limit=1)

            if key not in groups:
                groups[key] = {
                    'partner': partner,
                    'company': company,
                    'account': account,
                    'currency': currency,
                    'journal': journal,
                    'product': self.env['product.product'].search([
                        ('name', 'ilike', 'Redondeo')], limit=1),
                    'move_ids': self.env['account.move'],
                    'move_line_ids': self.env['account.move.line'],
                }

            groups[key]['move_ids'] |= move
            groups[key]['move_line_ids'] |= line

        return groups

    def _get_group_amount(self, lines, currency, company):
        if currency != company.currency_id:
            amount = sum(lines.mapped('amount_residual_currency'))
        else:
            amount = sum(lines.mapped('amount_residual'))
        return abs(amount)

    def _get_move_names(self, moves):
        names = [name for name in moves.mapped('name') if name and name != '/']
        if not names:
            return ''
        head = ', '.join(names[:8])
        if len(names) > 8:
            head += ' ...'
        return head

    def _build_description(self, move_ids):
        names = [name for name in move_ids.mapped('name') if name and name != '/']
        if not names:
            return _('Redondeo de saldo')

        if len(names) == 1:
            return _('Redondeo de saldo en %s') % names[0]

        shown = ', '.join(names[:5])
        if len(names) > 5:
            shown = '%s + %s' % (shown, len(names) - 5)

        return _('Redondeo de saldo en %s') % shown

    def action_confirm(self):
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_('No hay líneas para procesar.'))

        created_invoices = self.env['account.move']

        for wiz_line in self.line_ids.filtered(lambda l: l.amount_total > 0):
            company = wiz_line.company_id
            partner = wiz_line.partner_id
            account = wiz_line.account_id
            currency = wiz_line.currency_id
            journal = wiz_line.journal_id
            product = wiz_line.product_id


            if journal.company_id != company:
                raise UserError(_(
                    'El diario %s no pertenece a la compañía %s.'
                ) % (journal.display_name, company.display_name))

            if journal.type != 'sale':
                raise UserError(_(
                    'El diario %s debe ser de tipo Venta.'
                ) % journal.display_name)

            move_names = [name for name in wiz_line.move_ids.mapped('name') if name and name != '/']

            if move_names:
                texto_origen = 'El Redondeo de saldo en: %s' % ', '.join(move_names)
            else:
                texto_origen = 'El Redondeo de saldo en los asientos seleccionados'

            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'company_id': company.id,
                'journal_id': journal.id,
                'currency_id': currency.id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': product.id,
                        'quantity': 1.0,
                        'price_unit': wiz_line.amount_total,
                        'account_id': account.id,
                        'tax_ids': [(6, 0, [])],
                    }),
                    (0, 0, {
                        'display_type': 'line_note',
                        'name': texto_origen,
                    })
                ]
            }

            invoice = self.env['account.move'].with_company(company).create(invoice_vals)
            invoice.action_post()
            created_invoices |= invoice

        if not created_invoices:
            raise UserError(_('No se creó ninguna factura.'))

        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['domain'] = [('id', 'in', created_invoices.ids)]
        if len(created_invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = created_invoices.id
        return action


class AccountMoveRoundingInvoiceWizardLine(models.TransientModel):
    _name = 'account.move.rounding.invoice.wizard.line'
    _description = 'Wizard Line - Facturas de redondeo desde líneas contables'

    wizard_id = fields.Many2one(
        'account.move.rounding.invoice.wizard',
        required=True,
        ondelete='cascade'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
    )

    account_id = fields.Many2one(
        'account.account',
        string='Cuenta a cobrar',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
    )

    move_ids = fields.Many2many(
        'account.move',
        string='Movimientos origen',
    )

    move_line_ids = fields.Many2many(
        'account.move.line',
        string='Líneas origen',
    )

    move_count = fields.Integer(
        string='Cant. asientos',
    )

    line_count = fields.Integer(
        string='Cant. líneas',
    )

    amount_total = fields.Monetary(
        string='Importe a facturar',
        currency_field='currency_id',
    )

    move_names = fields.Char(
        string='Referencias',
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
    )

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
    )