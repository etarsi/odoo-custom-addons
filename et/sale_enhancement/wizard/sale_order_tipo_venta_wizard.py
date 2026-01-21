# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)

class SaleOrderTipoVentaWizard(models.TransientModel):
    _name = 'sale.order.tipo.venta.wizard'
    _description = 'Wizard: Modificatión Tipo de Venta, Compañía, Lista de Precios y Condición de Venta'

    sale_id = fields.Many2one('sale.order', string='Pedido de venta', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True)
    condicion_m2m_id = fields.Many2one('condicion.venta', string='Condición de Venta', required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de Precios', required=False, readonly=True, store=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        sale = self.env['sale.order'].browse(active_id)
        if not sale or sale._name != 'sale.order':
            raise UserError(_('Este asistente debe abrirse desde un pedido de venta.'))

        res.update({
            'sale_id': sale.id,
            'condicion_m2m_id': sale.condicion_m2m.id,
            'company_id': sale.company_id.id,
        })
        return res
            
    @api.onchange('company_id')
    def _onchange_company_id(self):
        if not self.company_id:
            return {}

        if self.company_id.id == 1:  # Producción B
            domain = {
                'condicion_m2m_id': [('name', '=', 'TIPO 3')],
                'pricelist_id': [('list_default_b', '=', True)],
            }
            # si no viene seteado desde default_get, lo seteo
            if self.condicion_m2m_id.name != 'TIPO 3':
                self.condicion_m2m_id = self.env['condicion.venta'].search([('name', '=', 'TIPO 3')], limit=1)
                self.pricelist_id = self.env['product.pricelist'].search([('list_default_b', '=', True)], limit=1)
        else:
            domain = {
                'condicion_m2m_id': [('name', '!=', 'TIPO 3')],
                'pricelist_id': [('is_default', '=', True)],
            }
            # si el valor actual no cumple el dominio, lo corrijo
            if self.condicion_m2m_id and self.condicion_m2m_id.name == 'TIPO 3':
                self.condicion_m2m_id = self.env['condicion.venta'].search([('name', '!=', 'TIPO 3')], limit=1)
                self.pricelist_id = self.env['product.pricelist'].search([('is_default', '=', True)], limit=1)
        return {'domain': domain}        

    def action_confirm(self):
        self.ensure_one()
        sale = self.sale_id
        pricelist_id = False
        if self.company_id.id == 1:  # Producción B
            pricelist_id = self.env['product.pricelist'].search([('list_default_b', '=', True)], limit=1)
        else:
            pricelist_id = self.env['product.pricelist'].search([('is_default', '=', True)], limit=1)  
        
        _logger.info('Asignando a pedido %s: compañía %s, condición venta %s, lista precios %s', sale.name, self.company_id.name, self.condicion_m2m_id.name, pricelist_id)
        if not pricelist_id:
            raise UserError(_('No se encontró una lista de precios válida para la compañía seleccionada.'))
        #cambiar el warehouse si corresponde
        warehouse = False
        if self.company_id.id == 1:  # Producción B
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', 1)], limit=1)
        else:
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        if not warehouse:
            raise UserError(_('No se encontró un almacén para la compañía %s. Verifique su configuración de Almacenes.') % self.company_id.name)

        sale.write({
            'company_default': self.company_id.id,
            'condicion_m2m': self.condicion_m2m_id.id,
            'pricelist_id': pricelist_id.id,
            'company_id': self.company_id.id,
            'warehouse_id': warehouse.id,
        })
        # agregar en el chat del pedido la modificación realizada y quien la hizo
        sale.message_post(body=_('Tipo de venta modificado a "%s", Compañía a "%s", Lista de Precios a "%s" por el usuario %s desde el asistente de modificación de tipo de venta.') % (
            self.condicion_m2m_id.name,
            self.company_id.name,
            pricelist_id.name,
            self.env.user.name,
        ))
        #recompute taxes
        sale._compute_tax_id()

        #modificar los stock pickings asociados si no estan done o cancelados
        pickings = sale.mapped('picking_ids').filtered(lambda p: p.state not in ('done', 'cancel'))
        for picking in pickings:       
            rule = self.env['stock.rule'].search([
                ('warehouse_id', '=', warehouse.id),
                ('location_src_id', '=', warehouse.lot_stock_id.id),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            #ahora los stock moves
            for move in picking.move_lines:
                vals_move = {
                    'rule_id': rule.id,
                    'company_id': self.company_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'warehouse_id': warehouse.id,
                    'picking_type_id': warehouse.out_type_id.id,
                }
                move.write(vals_move)
            #y los move lines
            for move_line in picking.move_line_ids:
                move_line.write({
                    'company_id': self.company_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                })
            #finalmente el picking
            picking.write({
                'company_id': self.company_id.id,
                'location_id': warehouse.lot_stock_id.id,
            })
            # forzar el cambio de nombre en pickings done
            #self.forzar_name_picking_done(picking, new_name)
            # agregar en el chat del picking la modificación realizada y quien la hizo
            picking.message_post(body=_('Compañía modificada a "%s" por el usuario %s desde el asistente de modificación de tipo de venta del pedido de venta asociado.') % (
                self.company_id.name,
                self.env.user.name,
            ))
        #Modificar las facturas asociadas si no estan posted o canceladas
        #picking en estado done 
        picking_dones = sale.mapped('picking_ids').filtered(lambda p: p.state == 'done')
        if picking_dones:
            for picking in picking_dones:
                if not picking.invoice_ids or (picking.invoice_ids and picking.mapped('invoice_ids').filtered(lambda inv: inv.state not in ('posted', 'cancel'))):
                    rule = self.env['stock.rule'].search([
                        ('warehouse_id', '=', warehouse.id),
                        ('location_src_id', '=', warehouse.lot_stock_id.id),
                        ('company_id', '=', self.company_id.id),
                    ], limit=1)
                    #ahora los stock moves
                    for move in picking.move_lines:
                        vals_move = {
                            'rule_id': rule.id,
                            'company_id': self.company_id.id,
                            'location_id': warehouse.lot_stock_id.id,
                            'warehouse_id': warehouse.id,
                            'picking_type_id': warehouse.out_type_id.id,
                        }
                        move.write(vals_move)
                    #y los move lines
                    for move_line in picking.move_line_ids:
                        move_line.write({
                            'company_id': self.company_id.id,
                            'location_id': warehouse.lot_stock_id.id,
                        })
                    #finalmente el picking
                    picking.write({
                        'company_id': self.company_id.id,
                        'location_id': warehouse.lot_stock_id.id,
                    })
                    # forzar el cambio de nombre en pickings done
                    #self.forzar_name_picking_done(picking, new_name)
                    # agregar en el chat del picking la modificación realizada y quien la hizo
                    picking.message_post(body=_('Compañía modificada a "%s" por el usuario %s desde el asistente de modificación de tipo de venta del pedido de venta asociado.') % (
                        self.company_id.name,
                        self.env.user.name,
                    ))
                    #ahora las facturas asociadas
                    if picking.invoice_ids:
                        invoices = picking.invoice_ids.filtered(lambda inv: inv.state not in ('posted', 'cancel'))
                        if invoices:
                            for invoice in invoices:
                                journal_id = self.env['account.journal'].search([
                                    ('type', '=', 'sale'),
                                    ('company_id', '=', self.company_id.id),
                                    ('code', '=', invoice.journal_id.code)], limit=1)
                                if not journal_id:
                                    raise UserError(_('No se encontró un diario de ventas para la compañía %s. Verifique su configuración de Diarios.') % self.company_id.name)
                                invoice.write({
                                    'journal_id': journal_id.id,
                                    'company_id': self.company_id.id,
                                })
                                #recompute taxes
                                invoice.update_taxes()
                                invoice._compute_amount()
                                # agregar en el chat de la factura la modificación realizada y quien la hizo
                                invoice.message_post(body=_('Compañía modificada a "%s" por el usuario %s desde el asistente de modificación de tipo de venta del pedido de venta asociado.') % (
                                    self.company_id.name, self.env.user.name,
                                ))
        return {'type': 'ir.actions.act_window_close'}
    
    
    def name_company(self, company_id):
        if company_id == 1:
            return 'PRD'
        elif company_id == 2:
            return 'SEBIG'
        elif company_id == 3:
            return 'BECHA'
        elif company_id == 4:
            return 'FUN T'

    def forzar_name_picking_done(self, picking, new_name):
        # forzar el cambio de nombre en pickings done
        picking_id = picking.id
        self.env.cr.execute("UPDATE stock_picking SET name=%s WHERE id=%s", (new_name, picking_id))