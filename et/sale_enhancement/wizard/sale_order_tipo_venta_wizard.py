# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math
from datetime import timedelta

class SaleOrderTipoVentaWizard(models.TransientModel):
    _name = 'sale.order.tipo.venta.wizard'
    _description = 'Wizard: Modificatión Tipo de Venta, Compañía, Lista de Precios y Condición de Venta'

    sale_id = fields.Many2one('sale.order', string='Pedido de venta', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True)
    condicion_m2m_id = fields.Many2one('condicion.venta', string='Condición de Venta', required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de Precios', required=False, readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        sale = self.env['sale.order'].browse(active_id)
        if not sale or sale._name != 'sale.order':
            raise UserError(_('Este asistente debe abrirse desde un pedido de venta.'))

        res.update({
            'sale_id': sale.id,
            'condicion_m2m_id': sale.condicion_m2m_id.id,
            'company_id': sale.company_id.id,
        })
        return res
            
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

    @api.onchange('condicion_m2m_id')
    def _onchange_condicion_m2m_id(self):
        if self.condicion_m2m_id:
            tipo = (self.condicion_m2m_id.name or '').upper().strip()
            if tipo == 'TIPO 3':
                return {'domain': {'company_id': [('id', '=', 1)], 'pricelist_id': [('list_default_b', '=', True)]}}
            else:
                return {'domain': {'company_id': [('id', '!=', 1)], 'pricelist_id': [('list_default_b', '!=', True)]}}

    def action_confirm(self):
        self.ensure_one()
        sale = self.sale_id
        sale.write({
            'company_default': self.company_id.id,
            'condicion_m2m_id': self.condicion_m2m_id.id,
            'pricelist_id': self.pricelist_id.id,
        })
        return {'type': 'ir.actions.act_window_close'}