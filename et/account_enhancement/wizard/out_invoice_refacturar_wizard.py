# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math
from datetime import timedelta

class OutInvoiceRefacturarWizard(models.TransientModel):
    _name = 'out.invoice.refacturar.wizard'
    _description = 'Wizard: Refacturar Facturas de Cliente'

    account_move_ids = fields.Many2many('account.move', string='Facturas', required=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True)
    condicion_m2m_id = fields.Many2one('condicion.venta', string='Condición de Venta', required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de precios', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'account.move':
            moves = self.env['account.move'].browse(self.env.context.get('active_ids', []))
            # quedate solo con facturas cliente
            moves = moves.filtered(lambda m: m.move_type == 'out_invoice')
            if not moves:
                raise UserError(_("Seleccioná al menos una factura de cliente."))
            res['account_move_ids'] = [(6, 0, moves.ids)]
        return res

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            domain = []
            domain2 = []
            self.condicion_m2m_id = False
            self.pricelist_id = False
            if self.company_id.id == 1:  # Producción B
                domain2 = [('is_default', '=', True)]
                domain = [('name', '=', 'TIPO 3')]
                self.condicion_m2m_id = self.env['condicion.venta'].search([('name', '=', 'TIPO 3')], limit=1)
                return {'domain': {'condicion_m2m_id': domain, 'pricelist_id': domain2}}
            else:
                self.condicion_m2m_id = self.env['condicion.venta'].search([('name', '=', 'TIPO 1')], limit=1)
                return {'domain': {'condicion_m2m_id': [('name', '=', 'TIPO 1')], 'pricelist_id': [('is_default', '!=', True)]}}

    def set_due_date_plus_x(self, x):
        today = fields.Date.context_today(self)
        new_date = today + timedelta(days=x)
        return new_date

    def _prepare_invoice_base_vals(self, company):
        invoice_date_due = fields.Date.context_today(self)

        if self.sale_id.payment_term_id:
            extra_days = max(self.sale_id.payment_term_id.line_ids.mapped('days') or [0])
            invoice_date_due = self.set_due_date_plus_x(extra_days)
        
        return {
            'move_type': 'out_invoice',
            'partner_id': 1,
            'partner_shipping_id': self.sale_id.partner_shipping_id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': invoice_date_due,
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'invoice_origin': self.sale_id.name,
            'payment_reference': self.sale_id.name,
            'fiscal_position_id': self.sale_id.partner_invoice_id.property_account_position_id.id,
            'invoice_payment_term_id': self.sale_id.payment_term_id,
            'wms_code': False,
        }

    def comparar_company_id(self, company_id):
        for move in self.account_move_ids:
            if move.company_id != company_id:
                return {'company_id': False, 'name': move.name}    
        return {'company_id': True}



    # ---------------- Core helpers ----------------

    def _map_taxes_to_company(self, taxes, company, partner_fp):
        """Mapea impuestos a la compañía destino.
        1) mismo nombre en esa compañía; si no,
        2) impuestos del producto en esa compañía; luego
        3) aplica fiscal position.
        """
        Tax = self.env['account.tax'].with_company(company)
        mapped = self.env['account.tax']
        for tax in taxes:
            cand = Tax.search([('name', '=', tax.name), ('type_tax_use', '=', tax.type_tax_use),
                               ('company_id', '=', company.id)], limit=1)
            if cand:
                mapped |= cand
        return partner_fp.map_tax(mapped) if partner_fp and mapped else mapped

    def _compute_price_with_pricelist(self, product, qty, pricelist, company, date):
        """Devuelve price_unit desde la lista. Si no hay lista, None."""
        if not (product and pricelist):
            return None
        return pricelist._get_product_price(
            product=product,
            quantity=qty or 1.0,
            currency=company.currency_id,
            date=date,
        )

    def _new_invoice_vals(self, move_src, company, pricelist):
        """Arma vals para nueva factura en 'company' a partir de 'move_src'."""
        partner = move_src.partner_id
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
        if not journal:
            raise UserError(_("No se encontró un diario de ventas en %s") % company.display_name)

        # Fiscal position del partner en la compañía destino
        fp = partner.property_account_position_id

        vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.context_today(self),
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'invoice_payment_term_id': move_src.invoice_payment_term_id.id,
            'invoice_origin': move_src.name,
            'payment_reference': move_src.payment_reference or move_src.name,
            'journal_id': journal.id,
            'invoice_line_ids': [],
        }

        for line in move_src.invoice_line_ids.filtered(lambda l: not l.display_type):
            # precio: si hay pricelist, recalculo; si no, dejo el de origen
            price_unit = self._compute_price_with_pricelist(
                product=line.product_id,
                qty=line.quantity,
                pricelist=pricelist,
                company=company,
                date=fields.Date.context_today(self),
            )
            if price_unit is None:
                price_unit = line.price_unit

            # impuestos: mapear por compañía y aplicar FP
            mapped_taxes = self._map_taxes_to_company(line.tax_ids, company, fp)
            if not mapped_taxes and line.product_id:
                # fallback: impuestos del producto en esa compañía
                prod_taxes = line.product_id.taxes_id.filtered(lambda t: t.company_id == company)
                mapped_taxes = fp.map_tax(prod_taxes) if fp and prod_taxes else prod_taxes

            vals['invoice_line_ids'].append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.quantity,
                'product_uom_id': line.product_uom_id.id,
                'price_unit': price_unit,
                'discount': line.discount,
                'tax_ids': [(6, 0, mapped_taxes.ids)],
            }))

        return vals

    # ---------------- Acción principal ----------------

    def action_create_invoice_from_out_invoice(self):
        self.ensure_one()

        new_invoices = self.env['account.move']
        credit_notes = self.env['account.move']

        for move in self.account_move_ids:
            if move.move_type != 'out_invoice':
                raise UserError(_("La factura %s no es de cliente.") % move.name)
            if move.state != 'posted':
                raise UserError(_("La factura %s debe estar Validada.") % move.name)
            company_comparacion = self.comparar_company_id(move.company_id)
            if not company_comparacion['company_id']:
                raise UserError(_("La factura %s debe pertenecer a la compañía seleccionada.") % (company_comparacion['name'],))

            # 1) Reverso (NC) en la compañía original
            #    cancel=True: crea NC y marca la original como cancelada/reconciliada (según configuración).
            reversal_vals = [{
                'ref': _('Refacturación de %s') % move.name,
                'date': fields.Date.context_today(self),
            }]
            credit_notes = move._reverse_moves(default_values_list=reversal_vals, cancel=True)

            # 2) Publicar SOLO las NC en borrador (evita "ya está publicado")
            draft_credits = credit_notes.filtered(lambda m: m.state == 'draft')
            if draft_credits:
                draft_credits.action_post()
            credit_notes |= draft_credits

            # 2) Nueva factura en la compañía destino
            vals = self._new_invoice_vals(move_src=move, company=self.company_id, pricelist=self.pricelist_id)
            new = self.env['account.move'].with_company(self.company_id).create(vals)
            new_invoices |= new

        # Mostrar nuevas facturas creadas
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['domain'] = [('id', 'in', new_invoices.ids)]
        return action