# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResidualInvoiceWizard(models.TransientModel):
    _name = 'residual.invoice.wizard'
    _description = 'Wizard - Facturas de redondeo desde asientos'

    line_ids = fields.One2many(
        'residual.invoice.line.wizard',
        'wizard_id',
        string='Líneas'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_ids = self.env.context.get('active_ids', [])
        moves = self.env['account.move'].browse(active_ids).exists()

        if not moves:
            raise UserError(_('No hay asientos seleccionados.'))

        not_posted = moves.filtered(lambda m: m.state != 'posted')
        if not_posted:
            raise UserError(_('Todos los movimientos seleccionados deben estar publicados.'))

        groups = self._group_selected_moves(moves)

        if not groups:
            raise UserError(_(
                'No se encontraron líneas pendientes en cuenta a cobrar con residual negativo '
                'para los movimientos seleccionados.'
            ))

        line_commands = []
        for data in groups.values():
            partner = data['partner']
            company = data['company']
            account = data['account']
            currency = data['currency']
            move_ids = data['move_ids']
            move_line_ids = data['move_line_ids']

            partner_receivable = partner.with_company(company).property_account_receivable_id
            if partner_receivable != account:
                raise UserError(_(
                    'El partner %s en la compañía %s tiene como cuenta a cobrar %s, '
                    'pero los movimientos seleccionados están pendientes en %s.\n\n'
                    'Para que la conciliación automática funcione, ambas deben coincidir.'
                ) % (
                    partner.display_name,
                    company.display_name,
                    partner_receivable.display_name if partner_receivable else _('(vacía)'),
                    account.display_name,
                ))

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
                'line_count': len(move_line_ids),
                'amount_total': amount_total,
                'move_names': self._get_move_names(move_ids),
            }))

        if not line_commands:
            raise UserError(_('No hay agrupaciones válidas para procesar.'))

        res['line_ids'] = line_commands
        return res

    def _group_selected_moves(self, moves):
        groups = {}

        for move in moves:
            candidate_lines = move.line_ids.filtered(self._is_candidate_line)

            for line in candidate_lines:
                partner = line.partner_id.commercial_partner_id
                company = line.company_id
                account = line.account_id
                currency = line.currency_id or line.company_currency_id

                key = (partner.id, company.id, account.id, currency.id)

                if key not in groups:
                    groups[key] = {
                        'partner': partner,
                        'company': company,
                        'account': account,
                        'currency': currency,
                        'move_ids': self.env['account.move'],
                        'move_line_ids': self.env['account.move.line'],
                    }

                groups[key]['move_ids'] |= move
                groups[key]['move_line_ids'] |= line

        return groups

    def _is_candidate_line(self, line):
        if not line.partner_id:
            return False

        if line.reconciled:
            return False

        if line.account_id.user_type_id.type != 'receivable':
            return False

        # Este flujo está pensado para créditos del cliente
        # que luego se consumen con una factura de redondeo.
        if line.currency_id and line.currency_id != line.company_currency_id:
            residual = line.amount_residual_currency
        else:
            residual = line.amount_residual

        return residual < -0.00001

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
            journal = self.env['account.journal'].search([('name', 'like', 'Reclasificacion'), ('company_id', '=', company.id)], limit=1)
            product = self.env['product.product'].search([('name', '=', 'Redondeo')], limit=1)

            if not journal:
                raise UserError(_(
                    'Falta configurar el Diario facturas redondeo en la compañía %s.'
                ) % company.display_name)

            if not product:
                raise UserError(_(
                    'Falta configurar el Producto redondeo en la compañía %s.'
                ) % company.display_name)

            if journal.company_id != company:
                raise UserError(_(
                    'El diario %s no pertenece a la compañía %s.'
                ) % (journal.display_name, company.display_name))

            if journal.type != 'sale':
                raise UserError(_(
                    'El diario %s debe ser de tipo Venta.'
                ) % journal.display_name)

            description = self._build_description(wiz_line.move_ids)

            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'company_id': company.id,
                'journal_id': journal.id,
                'currency_id': currency.id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_line_ids': [(0, 0, {
                    'product_id': product.id,
                    'name': description,
                    'quantity': 1.0,
                    'price_unit': wiz_line.amount_total,
                    'tax_ids': [(6, 0, [])],
                })],
            }

            invoice = self.env['account.move'].with_company(company).create(invoice_vals)
            invoice.action_post()

            new_receivable_lines = invoice.line_ids.filtered(
                lambda l: (
                    l.account_id.id == account.id
                    and l.partner_id.commercial_partner_id.id == partner.id
                    and not l.reconciled
                )
            )

            if not new_receivable_lines:
                raise UserError(_(
                    'La factura %s no generó una línea a cobrar en la cuenta %s.\n'
                    'Revisá la cuenta a cobrar del partner o la configuración contable.'
                ) % (invoice.display_name, account.display_name))

            old_lines = wiz_line.move_line_ids.filtered(lambda l: not l.reconciled)

            if not old_lines:
                raise UserError(_(
                    'Las líneas origen del partner %s ya están conciliadas.'
                ) % partner.display_name)

            (old_lines | new_receivable_lines).reconcile()

            created_invoices |= invoice

        if not created_invoices:
            raise UserError(_('No se creó ninguna factura.'))

        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['domain'] = [('id', 'in', created_invoices.ids)]

        if len(created_invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = created_invoices.id

        return action


class ResidualInvoiceLineWizard(models.TransientModel):
    _name = 'residual.invoice.line.wizard'
    _description = 'Wizard Line - Facturas de redondeo desde asientos'

    wizard_id = fields.Many2one(
        'residual.invoice.wizard',
        required=True,
        ondelete='cascade'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        readonly=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        readonly=True
    )

    account_id = fields.Many2one(
        'account.account',
        string='Cuenta a cobrar',
        required=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        readonly=True
    )

    move_ids = fields.Many2many(
        'account.move',
        string='Movimientos origen',
        readonly=True
    )

    move_line_ids = fields.Many2many(
        'account.move.line',
        string='Líneas origen',
        readonly=True
    )

    move_count = fields.Integer(
        string='Cant. asientos',
        readonly=True
    )

    line_count = fields.Integer(
        string='Cant. líneas',
        readonly=True
    )

    amount_total = fields.Monetary(
        string='Importe a facturar',
        currency_field='currency_id',
        readonly=True
    )

    move_names = fields.Char(
        string='Referencias',
        readonly=True
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        readonly=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        readonly=True
    )