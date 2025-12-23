# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, ValidationError
import math
from datetime import timedelta


EXPO_POS = {'FEERCEL', 'FEEWS', 'FEERCELP'}
class OutInvoiceRefacturarWizard(models.TransientModel):
    _name = 'out.invoice.refacturar.wizard'
    _description = 'Wizard: Refacturar Facturas de Cliente'

    account_move_ids = fields.Many2many('account.move', string='Facturas', required=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True)
    condicion_m2m_id = fields.Many2one('condicion.venta', string='Condición de Venta', required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de precios', required=True)
    accion = fields.Selection(
        [
            ('anular_refacturar', 'Anular y Refacturar'),
            ('solo_refacturar', 'Solo Refacturar'),
        ],
        string='Acción',
        required=True,
        default='anular_refacturar',
    )
    accion_descuento = fields.Boolean(string="Modificar Descuento", default=False, help="Permite modificar el descuento en las líneas de la nueva factura.")
    descuento_porcentaje = fields.Float(string="Descuento (%)", digits=(5, 2), help="Porcentaje de descuento a aplicar en las líneas de la nueva factura.")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'account.move':
            moves = self.env['account.move'].browse(self.env.context.get('active_ids', []))
            # quedate solo con facturas cliente
            moves = moves.filtered(lambda m: m.move_type == 'out_invoice')
            if not moves:
                raise ValidationError(_("Seleccioná al menos una factura de cliente."))
            res['account_move_ids'] = [(6, 0, moves.ids)]
        return res

    @api.onchange('accion_descuento')
    def _onchange_accion_descuento(self):
        if self.accion_descuento and len(self.account_move_ids) > 1:
            self.accion_descuento = False
            self.descuento_porcentaje = 0.0
            return {
                'warning': {
                    'title': _("Acción no permitida"),
                    'message': _("No se puede modificar el descuento cuando se seleccionan múltiples facturas."),
                }
            }
        
        if not self.accion_descuento:
            self.descuento_porcentaje = 0.0

    @api.onchange('descuento_porcentaje')
    def _onchange_descuento_porcentaje(self):
        if self.descuento_porcentaje < 0.0 or self.descuento_porcentaje > 100.0:
            raise ValidationError(_("El porcentaje de descuento debe estar entre 0 y 100."))

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            domain = []
            domain2 = []
            self.condicion_m2m_id = False
            self.pricelist_id = False
            if self.company_id.id == 1:  # Producción B
                domain2 = [('list_default_b', '=', True)]
                domain = [('name', '=', 'TIPO 3')]
                self.condicion_m2m_id = self.env['condicion.venta'].search([('name', '=', 'TIPO 3')], limit=1)
                return {'domain': {'condicion_m2m_id': domain, 'pricelist_id': domain2}}
            else:
                self.condicion_m2m_id = self.env['condicion.venta'].search([('name', '=', 'TIPO 1')], limit=1)
                self.pricelist_id = self.env['product.pricelist'].search([('is_default', '=', True)], limit=1)
                return {'domain': {'condicion_m2m_id': [('name', '=', 'TIPO 1')], 'pricelist_id': [('list_default_b', '!=', True)]}}

    def set_due_date_plus_x(self, x):
        today = fields.Date.context_today(self)
        new_date = today + timedelta(days=x)
        return new_date

    def comparar_company_id(self, company_id):
        for move in self.account_move_ids:
            if move.company_id != company_id:
                return {'company_id': False, 'name': move.name}    
        return {'company_id': True}


    # ---------------- Core helpers ----------------

    def _map_taxes_to_company(self, taxes, company, partner_fp, invoice_date):
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

    def _new_invoice_vals(self, move_src, company, pricelist):
        # Valores base (compruebo journal de venta)
        journal = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        if not journal:
            raise ValidationError(_("No se encontró un diario de ventas para la compañía %s. Por favor, configure uno.") % company.name)
        # Fiscal position del partner en la compañía destino
        fp = move_src.partner_id.property_account_position_id

        vals = {
            'move_type': 'out_invoice',
            'partner_id': move_src.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'invoice_payment_term_id': move_src.invoice_payment_term_id.id,
            'invoice_origin': move_src.name,
            'payment_reference': move_src.payment_reference or move_src.name,
            'journal_id': journal.id,
            'pricelist_id': self.pricelist_id.id,
            'special_price': move_src.special_price,
            'invoice_user_id': move_src.invoice_user_id.id,
            'invoice_line_ids': [],
        }

        for line in move_src.invoice_line_ids.filtered(lambda l: not l.display_type):
            # precio: si hay pricelist, recalculo; si no, dejo el de origen
            if move_src.special_price:
                price_unit = line.price_unit
            else:
                price_unit = pricelist.price_get(
                    line.product_id.id,
                    line.quantity or 1.0,
                )[pricelist.id]
                if not price_unit:
                    price_unit = line.price_unit
                    
            # Aplicar descuento si corresponde
            if self.accion_descuento:
                line_discount = self.descuento_porcentaje
                line.discount = line_discount
            # impuestos: mapear por compañía y aplicar FP
            mapped_taxes = self._map_taxes_to_company(line.tax_ids, company, fp, move_src.invoice_date)
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
                'sale_line_ids': [(6, 0, line.sale_line_ids.ids)],
            }))

        return vals

    # ---------------- Acción principal ----------------

    def action_create_invoice_from_out_invoice(self):
        self.ensure_one()

        new_invoices = self.env['account.move']
        credit_notes = self.env['account.move']

        for move in self.account_move_ids:
            if move.move_type != 'out_invoice':
                raise ValidationError(_("La factura %s no es de cliente.") % move.name)
            if move.state != 'posted':
                raise ValidationError(_("La factura %s debe estar Validada.") % move.name)
            company_comparacion = self.comparar_company_id(move.company_id)
            if not company_comparacion['company_id']:
                raise ValidationError(_("La factura %s debe pertenecer a la compañía seleccionada.") % (company_comparacion['name'],))
            
            # Valores para nueva factura       
            vals = self._new_invoice_vals(move_src=move, company=self.company_id, pricelist=self.pricelist_id)
            
            # Acción según selección   
            if self.accion == 'solo_refacturar':
                # 2) Nueva factura en la compañía destino
                new = self.env['account.move'].with_company(self.company_id).create(vals)
                new = new.with_context(check_move_validity=False)
                # Recomputar SIEMPRE: impuestos + cuenta a cobrar/pagar + términos de pago
                new.with_context(check_move_validity=False)
                new_invoices |= new
            elif self.accion == 'anular_refacturar':
                existing_refunds = move.reversal_move_id.filtered(lambda m: m.move_type == 'out_refund' and m.state in ('draft', 'posted'))
                if existing_refunds:
                    raise ValidationError(_(
                        "La factura %(invoice)s ya tiene una Nota de Crédito de reverso (%(refund)s) en estado %(state)s. "
                        "No se puede volver a refacturar."
                    ) % {
                        'invoice': move.name,
                        'refund': ', '.join(existing_refunds.mapped('name')),
                        'state': ', '.join(existing_refunds.mapped('state')),
                    })
                if move.payment_state == 'reversed':
                    raise ValidationError(_("La factura %s ya fue refacturada, no se puede volver a refacturar.") % move.name)
  
                reversal_vals = [{
                    'ref': _('Refacturación de %s') % move.name,
                    'date': fields.Date.context_today(self),
                }]

                # 1) Reverso (NC) en la compañía original
                code_comprobante_factura = move.l10n_latam_document_type_id.code
                if code_comprobante_factura == '1':
                    code_nc = self.env['l10n_latam.document.type'].search([('code', '=', '3'), ('internal_type', '=', 'credit_note')], limit=1)
                    if not code_nc:
                        raise ValidationError(_("No se encontró el tipo de comprobante Nota de Crédito (3) para refacturar la factura %s.") % move.name)
                    reversal_vals[0].update({'l10n_latam_document_type_id': code_nc.id})

                elif code_comprobante_factura == '201':
                    code_nc = self.env['l10n_latam.document.type'].search([('code', '=', '203'), ('internal_type', '=', 'credit_note')], limit=1)
                    if not code_nc:
                        raise ValidationError(_("No se encontró el tipo de comprobante Nota de Crédito (203) para refacturar la factura %s.") % move.name)  
                    reversal_vals[0].update({'l10n_latam_document_type_id': code_nc.id, 'afip_fce_es_anulacion': True})

                credit_notes = move._reverse_moves(default_values_list=reversal_vals, cancel=True)
                # 2) Publicar SOLO las NC en borrador (evita "ya está publicado")
                draft_credits = credit_notes.filtered(lambda m: m.state == 'draft')
                if draft_credits:
                    for draft_credit in draft_credits:
                        if draft_credit.l10n_latam_document_type_id.internal_type != 'credit_note':
                            internal_type = draft_credit.l10n_latam_document_type_id.internal_type or 'No está definido'
                            raise ValidationError(_("Se esperaba una Nota de Crédito, pero el tipo comprobante es: %s.") % internal_type)
                    draft_credits.action_post()
                credit_notes |= draft_credits

                # 2) Nueva factura en la compañía destino
                new = self.env['account.move'].with_company(self.company_id).with_context(check_move_validity=False).create(vals)
                # Recomputar SIEMPRE: impuestos + cuenta a cobrar/pagar + términos de pago
                new.with_context(check_move_validity=False)._recompute_dynamic_lines(recompute_all_taxes=True)
                # Validación final (acá sí querés que explote si queda mal)
                new._check_balanced()
                new_invoices |= new

        # Mostrar nuevas facturas creadas
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        if len(new_invoices) == 1:
            action = {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'views': [(self.env.ref('account.view_move_form').id, 'form')],
                'target': 'current',
                'res_id': new_invoices.id,
                'context': dict(self.env.context, default_move_type='out_invoice'),
            }
        else:
            action = {
                'type': 'ir.actions.act_window',
                'name': 'Facturas de Cliente',
                'res_model': 'account.move',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', new_invoices.ids)],
                'target': 'current',
                'context': dict(self.env.context, search_default_customer=1, default_move_type='out_invoice'),
            }
        return action