# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math

class SaleRefacturarWizard(models.TransientModel):
    _name = 'sale.refacturar.wizard'
    _description = 'Wizard: Refacturar Facturación desde Pedido de Venta'

    sale_id = fields.Many2one('sale.order', string='Pedido de venta', required=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True)
    condicion_m2m_id = fields.Many2one('condicion.venta', string='Condición de Venta', required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de precios', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        sale = self.env['sale.order'].browse(active_id)
        if not sale or sale._name != 'sale.order':
            raise UserError(_('Este asistente debe abrirse desde un pedido de venta.'))

        res.update({
            'sale_id': sale.id,
            'partner_id': sale.partner_id.id,
            # company_id vacío (None) por requerimiento
            # move_type vacío (None) por requerimiento
            # pricelist_id vacío (None) por requerimiento
        })
        return res
    
    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            domain = []
            self.condicion_m2m_id = False
            if self.company_id.id == 1:  # Producción B
                domain = [('name', '=', 'TIPO 3')]
                return {'domain': {'condicion_m2m_id': domain}}
            else:
                return {'domain': {'condicion_m2m_id': [('name', '!=', 'TIPO 3')]}}

    def action_confirm(self):
        self.ensure_one()
        SaleOrder = self.sale_id
        if not SaleOrder:
            raise UserError("La transferencia no está vinculada a ningún pedido de venta.")

        tipo = (self.condicion_m2m_id.name or '').upper().strip()
        proportion_blanco, proportion_negro = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }.get(tipo, (1.0, 0.0))

        company_blanca = self.company_id
        company_negra = self.env['res.company'].browse(1)

        invoice_lines_blanco = []
        invoice_lines_negro = []
        sequence = 1

        for move in self.move_ids_without_package:
            base_vals = move.sale_line_id._prepare_invoice_line(sequence=sequence)

            qty_total = move.quantity_done
            qty_blanco = math.floor(qty_total * proportion_blanco)
            qty_negro = qty_total - qty_blanco

            if proportion_blanco > 0:
                blanco_vals = base_vals.copy()
                blanco_vals['quantity'] = qty_blanco
                # blanco_vals['tax_ids'] = False
                blanco_vals['company_id'] = company_blanca.id

                taxes = move.sale_line_id.tax_id
                blanco_vals['tax_ids'] = [(6, 0, taxes.ids)] if taxes else False


                invoice_lines_blanco.append((0, 0, blanco_vals))

            if proportion_negro > 0:
                negro_vals = base_vals.copy()
                negro_vals['quantity'] = qty_negro
                negro_vals['company_id'] = company_negra.id
                if tipo == 'TIPO 3':
                    negro_vals['price_unit'] *= 1
                else:
                    negro_vals['price_unit'] *= 1.21
                
                negro_vals['tax_ids'] = False
                invoice_lines_negro.append((0, 0, negro_vals))

            sequence += 1

        invoices = self.env['account.move']

        # Crear factura blanca
        if invoice_lines_blanco:            
            vals_blanco = self._prepare_invoice_base_vals(company_blanca)

            vals_blanco['invoice_line_ids'] = invoice_lines_blanco
            vals_blanco['invoice_user_id'] = self.sale_id.user_id
            vals_blanco['partner_bank_id'] = False            
            vals_blanco['company_id'] = company_blanca.id

            if not vals_blanco.get('journal_id'):
                journal = self.env['account.journal'].search([
                    ('type', '=', 'sale'),
                    ('company_id', '=', company_blanca.id)
                ], limit=1)
                if not journal:
                    raise UserError(f"No se encontr\u00f3 un diario de ventas para la compa\u00f1\u00eda {self.company_id.name}.")
                vals_blanco['journal_id'] = journal.id

            invoices += self.env['account.move'].with_company(company_blanca).create(vals_blanco)

        # Crear factura negra
        if invoice_lines_negro:
            vals_negro = self._prepare_invoice_base_vals(company_negra)
            vals_negro['invoice_line_ids'] = invoice_lines_negro
            vals_negro['invoice_user_id'] = self.sale_id.user_id                        
            vals_negro['company_id'] = company_negra

            # Asignar journal correcto
            journal = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', company_negra.id)
            ], limit=1)
            if not journal:
                raise UserError("No se encontró un diario de ventas para Producción B.")
            vals_negro['journal_id'] = journal.id
            vals_negro['partner_bank_id'] = False

            invoices += self.env['account.move'].with_company(company_negra).create(vals_negro)

        # Relacionar con la transferencia
        invoices.write({
            'invoice_origin': self.origin or self.name,
        })

        self.invoice_ids = [(6, 0, invoices.ids)]

        self.invoice_state = 'invoiced'
        for move in self.move_ids_without_package.filtered(lambda m: m.sale_line_id):
            move.sale_line_id.qty_invoiced += move.quantity_done
            move.invoice_state = 'invoiced'
            
        if len(self.invoice_ids) == 1:
            return {
                'name': "Factura generada",
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.invoice_ids[0].id,
            }
        else:
            return {
                'name': "Facturas generadas",
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', self.invoice_ids.ids)],
            }
    
    def _prepare_invoice_base_vals(self, company):
        partner = self.partner_id
        invoice_date_due = fields.Date.context_today(self)

        if self.sale_id.payment_term_id:
            extra_days = max(self.sale_id.payment_term_id.line_ids.mapped('days') or [0])
            invoice_date_due = self.set_due_date_plus_x(extra_days)
        
        return {
            'move_type': 'out_invoice',
            'partner_id': self.sale_id.partner_invoice_id,
            'partner_shipping_id': self.sale_id.partner_shipping_id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': invoice_date_due,
            'company_id': self.sale_id.company_id.id,
            'currency_id': self.sale_id.company_id.currency_id.id,
            'invoice_origin': self.origin or self.name,
            'payment_reference': self.name,
            'fiscal_position_id': self.sale_id.partner_invoice_id.property_account_position_id.id,
            'invoice_payment_term_id': self.sale_id.payment_term_id,
            'wms_code': self.codigo_wms,
        }