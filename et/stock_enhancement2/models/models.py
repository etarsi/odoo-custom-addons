from odoo import models, fields, api, _
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
import logging
import math
import requests
from itertools import groupby
from datetime import timedelta

_logger = logging.getLogger(__name__)

class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    wms_date = fields.Date(string="Fecha WMS")
    has_peluches = fields.Boolean(string="Peluches", compute="_compute_has_peluches")
    has_makeup = fields.Boolean(string="Maquillaje", compute="_compute_has_makeup", store=True)
    has_pistolas_agua = fields.Boolean(string="Pistolas de Agua", compute="_compute_has_pistolas_agua", store=True)
    has_vehiculos = fields.Boolean(string="Vehiculos", compute="_compute_has_vehiculos", store=True)
    has_rodado = fields.Boolean(string="Rodados", compute="_compute_has_rodado", store=True)
    has_rodado_infantiles = fields.Boolean(string="Rodados Infantiles", compute="_compute_has_rodado_infantiles", store=True)
    has_toys = fields.Boolean(string="Juguetes", compute="_compute_has_toys", store=True)
    has_balls = fields.Boolean(string="Pelotas", compute="_compute_has_balls", store=True)
    has_pop = fields.Boolean(string="POP", compute="_compute_has_pop", store=True)
    available_pkg_qty = fields.Float(string='Bultos Disponibles' ,compute='sum_bultos', group_operator='sum', store=True)
    partner_delivery_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Transportista del cliente',
        store=True,
        readonly=True,
        default=lambda self: self._default_delivery_carrier()
    )
    invoice_ids = fields.Many2many(
        'account.move',
        'stock_picking_invoice_rel',
        'picking_id',
        'invoice_id',
        string='Facturas relacionadas'
    )

    old_picking = fields.Boolean(default=False)
    old_picking_txt = fields.Text(default='⚠️ PICKING VIEJO - FACTURAR E IMPRIMIR REMITO DE LA VIEJA FORMA')

    delivery_state = fields.Selection(selection=[('no', 'No entregado'), ('delivered', 'Entregado'), ('returned', 'Devuelto')], default='no', copy=False, string='Estado Delivery')
    china_purchase = fields.Boolean(default=False, copy=True)
    wesend_ids = fields.Char(string="Remitos")
    remito_compartido = fields.Boolean(string="Remito Compartido", default=False)

    def action_correction_secuence(self):
        return True

    def assign_lots(self):
        for record in self:
            for move in record.move_ids_without_package:
                if move.quantity_done > 0:
                    lot = self.env['stock.production.lot'].search([
                        ('product_id', '=', move.product_id.id),
                        ('company_id', '=', move.company_id.id)
                    ], order='id asc', limit=1)

                    if lot:
                        for ml in move.move_line_ids:
                            ml.lot_id = lot.id
                        
                        if not move.move_line_ids:
                            move.move_line_ids.create({
                                'move_id': move.id,
                                'product_id': move.product_id.id,
                                'lot_id': lot.id,
                                'qty_done': move.quantity_done,
                                'location_id': move.location_id.id,
                                'location_dest_id': move.location_dest_id.id,
                                'product_uom_id': move.product_uom.id,
                            })
                    else:
                        lot_name = record.get_lot_name(move)
                        lot = record.create_lots(move, lot_name)

                        if lot:
                            for ml in move.move_line_ids:
                                ml.lot_id = lot.id
                            
                            if not move.move_line_ids:
                                move.move_line_ids.create({
                                    'move_id': move.id,
                                    'product_id': move.product_id.id,
                                    'lot_id': lot.id,
                                    'qty_done': move.quantity_done,
                                    'location_id': move.location_id.id,
                                    'location_dest_id': move.location_dest_id.id,
                                    'product_uom_id': move.product_uom.id,
                                })
                        else:
                            raise UserError(f'No hay lotes para el código: {move.product_id.default_code}')
            move.state = 'assigned'
                    

    def get_lot_name(self, move):
        incoming_types = self.env['stock.picking.type'].search([('code', '=', 'incoming')])
        incoming_type_ids = incoming_types.ids
        last_incoming_move = self.env['stock.move'].search([
            ('product_id', '=', move.product_id.id),
            ('picking_id.picking_type_id', 'in', incoming_type_ids),
        ], order='date desc', limit=1)

        if last_incoming_move:
            dispatch_number = last_incoming_move.picking_id.dispatch_number or ''
            lot_name = dispatch_number.split()[0] if dispatch_number else ''
            if lot_name != '':
                return lot_name
            else:
                raise UserError(f'No hay lotes para el código: {move.product_id.default_code}')
        else:
            raise UserError(f'No hay lotes para el código: {move.product_id.default_code}')
                    
                
    def create_lots(self, move, lot_name):
        company_ids = [1, 2, 3, 4]
        new_lots = []
        product_id = move.product_id
        self.check_product_lot(product_id)

        for cid in company_ids:
            lot_exist = self.env['stock.production.lot'].search([
                ('product_id', '=', move.product_id.id),
                ('company_id', '=', cid),
                ('name', '=', lot_name),
            ], limit=1)

            if not lot_exist:
                vals = {
                    'name': lot_name,
                    'product_id': move.product_id.id,
                    'ref': move.product_id.default_code,
                    'dispatch_number': lot_name,
                    'company_id': cid,
                }
                new_lot = self.env['stock.production.lot'].create(vals)
                new_lots.append(new_lot)

        for lot in new_lots:
            if lot.company_id.id == move.company_id.id:
                return lot

    def check_product_lot(self, product_id):
        if product_id.tracking != 'lot':
            product_id.tracking = 'lot'

    
    def mark_as_delivered(self):
        for record in self:
            record.delivery_state = 'delivered'

            if record.picking_type_code == 'outgoing':
                move_type = 'ENTREGA'
                record.action_create_product_moves(move_type)

                record.consume_stock()


    def update_availability(self):
        for record in self:
            if record.move_ids_without_package:
                for move in record.move_ids_without_package:

                    default_code = move.product_id.default_code
                    if default_code:
                        if default_code.startswith('9'):
                            search_code = default_code[1:]
                        else:
                            search_code = default_code

                    stock_erp = self.env['stock.erp'].search([
                            ('product_id.default_code', '=', search_code)
                        ], limit=1)
                    
                    if not stock_erp:
                            raise UserError(f'El producto [{default_code}]{move.product_id.name} no se encuentra en el listado de Stock. Avise al administrador.')
              

                    if move.product_uom_qty == 0:
                        available_percent = 0
                    
                    elif stock_erp.entregable_unidades >= move.product_uom_qty:
                        available_percent = 100
                        move.product_available_pkg_qty = move.product_packaging_qty
                        move.quantity_done = move.product_uom_qty

                    elif stock_erp.entregable_unidades == 0:
                        available_percent = 0
                        move.product_available_pkg_qty = 0
                        move.quantity_done = 0
                    else:

                        move.quantity_done = stock_erp.entregable_unidades
                        available_percent = (stock_erp.entregable_unidades * 100) / move.product_uom_qty
                        move.product_available_pkg_qty = move.quantity_done / move.product_packaging_id.qty

                    move.product_available_percent = available_percent

                pkg_qty = record.move_ids_without_package.mapped('product_packaging_qty')
                u_values = record.move_ids_without_package.mapped('product_available_percent')
                u_avg = (sum(u_values) / len(u_values)) if u_values else 0
                pkg_qty_sum = sum(pkg_qty)
                bultos = record.move_ids_without_package.mapped('product_available_pkg_qty')
                bultos_sum = sum(bultos)

                record.packaging_qty = pkg_qty_sum
                record.available_pkg_qty = bultos_sum
                record.available_percent = round(u_avg, 2)
                
                record.update_bultos()


    def update_bultos(self):
        for record in self:
            bultos = 0
            for move in record.move_ids_without_package:
                move.product_packaging_qty = move.product_uom_qty / move.product_packaging_id.qty
                bultos += move.product_packaging_qty
            record.packaging_qty = bultos

    def consume_stock(self):
        for record in self:
            vals_list = []

            if record.move_ids_without_package:
                for move in record.move_ids_without_package:
                    vals = {}
                    default_code = move.product_id.default_code

                    if default_code:
                        if default_code.startswith('9'):
                            search_code = default_code[1:]
                        else:
                            search_code = default_code

                        stock_erp = self.env['stock.erp'].search([
                            ('product_id.default_code', '=', search_code)
                        ], limit=1)

                        if not stock_erp:
                            raise UserError(f'El producto [{default_code}]{move.product_id.name} no se encuentra en el listado de Stock. Avise al administrador.')
                        
                        vals['stock_erp'] = stock_erp.id
                    else:
                        raise UserError(f'El producto {move.product_id.name} no tiene definido un código interno (default_code).')

                    for stock_move in stock_erp.move_lines:
                        if stock_move.sale_line_id.id == move.sale_line_id.id:
                            stock_move.quantity_delivered += move.quantity_done


                    vals['picking_id'] = record.id
                    vals['sale_id'] = record.sale_id.id
                    vals['sale_line_id'] = move.sale_line_id.id
                    vals['partner_id'] = record.sale_id.partner_id.id
                    vals['product_id'] = move.product_id.id
                    vals['quantity'] = move.quantity_done
                    vals['uxb'] = move.product_packaging_id.qty or ''
                    vals['bultos'] = move.product_packaging_qty
                    vals['type'] = 'delivery'

                    vals_list.append(vals)
            self.env['stock.moves.erp'].create(vals_list)

            

    def mark_as_returned(self):
        for record in self:
            record.delivery_state = 'returned'

    def button_validate(self):
        res = super().button_validate()

        for record in self:
            
            record.invoice_state = '2binvoiced'
            for move in record.move_ids_without_package:
                move.invoice_state = '2binvoiced'


            if record.partner_id.property_delivery_carrier_id.name != 'Reparto Propio':
                total_declarado = 0
                for move in record.move_ids_without_package:

                    price_unit = move.sale_line_id.price_unit
                    line_value = move.product_uom_qty * price_unit

                    total_declarado += line_value
                
                record.declared_value = total_declarado * 0.25

            if record.picking_type_code == 'incoming':
                move_type = 'RECEPCIÓN'
                record.action_create_product_moves(move_type)

        return res
    
    def action_create_product_moves(self, move_type):
        vals_list = []

        for picking in self:
            for move in picking.move_ids_without_package:
                for line in move.move_line_ids:
                    vals = {
                        'date': fields.Datetime.now(),
                        'type': move_type,
                        'product_id': move.product_id.id,
                        'product_code': move.product_id.default_code,
                        'product_name': move.product_id.name,
                        'categ_id': move.product_id.categ_id.name or '',
                        'quantity': line.qty_done,
                        'uxb': move.product_id.packaging_ids[:1].name if move.product_id.packaging_ids else '',
                        'lot': line.lot_id.name or '',
                        'cmv': '',
                        'partner_id': picking.partner_id.id,
                        'company_id': picking.company_id.name,
                        'picking_id': picking.id,
                        'wms_code': picking.codigo_wms,
                        'license': picking.carrier_tracking_ref,
                        'container': picking.container,
                        'dispatch': picking.dispatch_number,
                    }
                    vals_list.append(vals)

        self.env['product.move'].create(vals_list)



    def action_create_invoice_from_picking(self):
        self.ensure_one()

        SaleOrder = self.sale_id
        if not SaleOrder:
            raise UserError("La transferencia no está vinculada a ningún pedido de venta.")

        tipo = (self.x_order_type.name or '').upper().strip()
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
    
    def action_create_invoice_from_picking2(self):
        self.ensure_one()

        if not self.sale_id:
            raise UserError("La transferencia no está vinculada a ningún pedido de venta.")

        company = self.company_id
        tipo = (self.x_order_type.name or '').upper().strip()
        proportion = 1.0

        if tipo in ['TIPO 2', 'TIPO 4']:
            _logger.info("Pedido viejo TIPO %s detectado. Se factura 100%% en la compa\u00f1\u00eda del picking (%s)", tipo, company.name)

        invoice_lines = []
        sequence = 1

        for move in self.move_ids_without_package:
            if not move.sale_line_id:
                continue

            base_vals = move.sale_line_id._prepare_invoice_line(sequence=sequence)
            line_vals = base_vals.copy()
            line_vals['company_id'] = company.id
            line_vals['quantity'] = move.quantity_done

            taxes = move.sale_line_id.tax_id
            if company.id == 1:
                line_vals['tax_ids'] = False        
            else:
                line_vals['tax_ids'] = [(6, 0, taxes.ids)] if taxes else False

            # if tipo == 'TIPO 3':
            #     line_vals['price_unit'] *= 1.21
            # else:
            #     line_vals['price_unit'] *= 1

            invoice_lines.append((0, 0, line_vals))
            sequence += 1

        if not invoice_lines:
            raise UserError("No se encontraron l\u00edneas facturables en la transferencia.")

        invoice_vals = self._prepare_invoice_base_vals(company)
        invoice_vals['invoice_user_id'] = self.sale_id.user_id
        invoice_vals['invoice_line_ids'] = invoice_lines
        invoice_vals['company_id'] = company.id
        invoice_vals['partner_bank_id'] = False
        
               
        if not invoice_vals.get('journal_id'):
            journal = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', company.id)
            ], limit=1)
            if not journal:
                raise UserError(f"No se encontr\u00f3 un diario de ventas para la compa\u00f1\u00eda {company.name}.")
            invoice_vals['journal_id'] = journal.id

        invoice = self.env['account.move'].with_company(company).create(invoice_vals)

        invoice.write({
            'invoice_origin': self.origin or self.name,
        })

        self.invoice_ids = [(6, 0, invoice.ids)]
        self.invoice_state = 'invoiced'

        for move in self.move_ids_without_package.filtered(lambda m: m.sale_line_id):
            move.sale_line_id.qty_invoiced += move.quantity_done
            move.invoice_state = 'invoiced'

        return {
            'name': "Factura generada",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
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
    
    def set_due_date_plus_x(self, x):
        today = fields.Date.context_today(self)
        new_date = today + timedelta(days=x)
        return new_date

    def _default_delivery_carrier(self):        
        return self.partner_id.property_delivery_carrier_id.id
    
    def update_available_percent(self):
        all_product_codes = set()

        for record in self:
            for move in record.move_ids_without_package:
                all_product_codes.add(move.product_id.default_code)

        stock_data = self._get_stock_en_lotes(all_product_codes, max_por_lote=387)

        stock_by_code = {
            p['codigo']: p['stock']['disponible']
            for p in stock_data
        }


        if not stock_by_code:
            raise UserError('No hay nada disponible para ningún producto')

        for record in self:
            for move in record.move_ids_without_package:
                code = move.product_id.default_code
                disponible = stock_by_code.get(code, 0)

                if move.product_uom_qty == 0:
                    available_percent = 0
                    available_bultos = 0
                elif disponible >= move.product_uom_qty:
                    available_percent = 100
                    available_bultos = move.product_uom_qty / move.product_packaging_id.qty
                    move.quantity_done = move.product_uom_qty
                elif disponible == 0:
                    available_percent = 0
                    available_bultos = 0
                    move.quantity_done = 0
                else:
                    move.quantity_done = disponible
                    available_percent = (disponible * 100) / move.product_uom_qty
                    if move.product_packaging_id.qty > 0:
                        available_bultos = move.product_uom_qty / move.product_packaging_id.qty
                    else:
                        raise UserError(f'NO SE PUEDE ACTUALIZAR EL DISPONIBLE. Revise la transferencia {record.name}. Revise la línea del producto {move.product_id}')

                move.product_available_percent = available_percent
                move.product_available_pkg_qty = available_bultos
                if move.product_packaging_id.qty > 0:
                    move.product_packaging_qty = move.product_uom_qty / move.product_packaging_id.qty


            pkg_qty = record.move_ids_without_package.mapped('product_packaging_qty')
            u_values = record.move_ids_without_package.mapped('product_available_percent')
            u_avg = (sum(u_values) / len(u_values)) if u_values else 0
            bultos = record.move_ids_without_package.mapped('product_available_pkg_qty')
            bultos_sum = sum(bultos)
            pkg_qty_sum = sum(pkg_qty)

            record.packaging_qty = pkg_qty_sum
            record.available_percent = round(u_avg, 2)
            record.available_pkg_qty = bultos_sum

    def _get_stock_en_lotes(self, product_codes, max_por_lote=387):
        product_codes = list(product_codes)
        resultados_totales = []

        for i in range(0, len(product_codes), max_por_lote):
            lote = product_codes[i:i + max_por_lote]
            _logger.info(f"[STOCK] Llamando API para lote {i // max_por_lote + 1} con {len(lote)} códigos")
            respuesta = self._get_stock(lote)
            if respuesta:
                resultados_totales.extend(respuesta)

        return resultados_totales       
    
    def _get_stock(self, product_codes):
        headers = {}
        params = {}
        
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms-v2.url')
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        params = {'ArticuloCodigo': product_codes}       
        response = requests.get(f'{url}/v2/Stock/Tipo', headers=headers, params=params)

        if response.status_code == 200:
            products = response.json()
            if products:
                return products

        elif response.status_code == 400:
            raise UserError('ERROR: 400 BAD REQUEST. Avise a su administrador de sistema.')
        elif response.status_code == 404:
            raise UserError('ERROR: 404 NOT FOUND. Avise a su administrador de sistema.')
        elif response.status_code == 500:
            raise UserError('ERROR: 500 INTERNAL SERVER ERROR. Avise a su administrador de sistema. Probablemente alguno de los productos no se encuentra creado en Digip.')

    @api.depends('move_ids_without_package')
    def _compute_has_rodado(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 320:
                    record.has_rodado = True

    @api.depends('move_ids_without_package')
    def _compute_has_toys(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 218:
                    record.has_toys = True

    @api.depends('move_ids_without_package')
    def _compute_has_balls(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 778:
                    record.has_balls = True

    @api.depends('move_ids_without_package')
    def _compute_has_peluches(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 243:
                    record.has_peluches = True

    @api.depends('move_ids_without_package')
    def _compute_has_makeup(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 244:
                    record.has_makeup = True


    @api.depends('move_ids_without_package')
    def _compute_has_pistolas_agua(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 324:
                    record.has_pistolas_agua = True


    @api.depends('move_ids_without_package')
    def _compute_has_vehiculos(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 774:
                    record.has_vehiculos = True

    @api.depends('move_ids_without_package')
    def _compute_has_rodado_infantiles(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 780:
                    record.has_rodado_infantiles = True

    @api.depends('move_ids_without_package')
    def _compute_has_pop(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 763:
                    record.has_pop = True
    # def enviar(self):
    #     res = super().enviar()
    #     for record in self:
    #         record.wms_date = fields.Date.today()

    #     return res

    # def ajustar_fecha(self):
    #     for record in self:
    #         record.wms_date = fields.Date.today()
    
    def action_enviar_compartido(self):
        for record in self:
            if record.remito_compartido:
                raise ValidationError(_("El remito ya fue enviado al compartido anteriormente."))
            direccion_entrega = ""
            if record.carrier_id:
                if record.carrier_id.name == 'Reparto Propio':
                    direccion_entrega = f"{record.partner_id.street or '-'}, {record.partner_id.zip or '-'}, {record.partner_id.city or '-' }"
                else:
                    direccion_entrega = record.carrier_id.address
            try:
                values = [
                    "",                                          # A
                    self._fmt_dt_local(record.scheduled_date),   # B
                    record.codigo_wms or "",                     # C
                    record.origin or "",                         # D
                    record.name or "",                           # E
                    record.partner_id.name or "",                # F
                    (record.packaging_qty or ""),                # G
                    len(record.move_ids_without_package) or 0,   # H
                    "",                                        # I
                    record.partner_id.industry_id.name or "",    # J
                    "", "", "", "",                            # K L M N
                    "", "",                                        # O P
                    record.partner_id.industry_id.name or "",    # Q
                    record.carrier_id.name or "",                # R
                    direccion_entrega,                           # S
                    record.partner_id.street or "",              # T
                    record.partner_id.zip or "",                 # U
                    record.partner_id.city or "",                # V
                    "0",                                         # W
                    record.company_id.name or "",                # X
                ]
                enviado = record.env["google.sheets.client"].append_row(values)
                if enviado == 200:
                    record.remito_compartido = True
            except Exception as e:
                # Si preferís no romper el flujo, logueá y no levantes error
                _logger.exception("Fallo enviando a Google Sheets para %s", record.name)
                raise ValidationError(_("Fallo enviando a Google Sheets para picking %s: %s") % (record.name, e))

    def _fmt_dt_local(self, dt):
        """datetime -> string en zona del usuario."""
        if not dt:
            return ""
        dt_local = fields.Datetime.context_timestamp(self, dt)  # tz del usuario
        return dt_local.strftime('%d/%m/%Y')

    def split_auto(self):
        for picking in self:
            selected_moves = self.env['stock.move']
            line_count = 0
            bulto_count = 0

            for move in picking.move_ids_without_package:
                if move.product_available_percent == 100:
                    if line_count > 29 or bulto_count >= 25:
                        break
                    
                    bulto_qty = bulto_count + move.product_packaging_qty
                    if bulto_qty <= 30:      
                        line_count += 1
                        bulto_count += move.product_packaging_qty
                        selected_moves |= move

            if selected_moves:
                return picking._split_off_moves(selected_moves)
        return False
    
    def split_auto_multiple(self):
        all_new_pickings = self.env['stock.picking']
        for picking in self:
            while True:
                selected_moves = self.env['stock.move']
                line_count = 0
                bulto_count = 0
                moves_to_split = picking.move_ids_without_package.filtered(lambda m: m.product_available_percent == 100)

                for move in moves_to_split:
                    if line_count >= 30 or bulto_count >= 25:
                        break
                    if bulto_count + move.product_packaging_qty > 30:
                        continue
                    line_count += 1
                    bulto_count += move.product_packaging_qty
                    selected_moves |= move

                if not selected_moves:
                    break
                if len(selected_moves) == len(picking.move_ids_without_package):
                    break

                new_picking = picking._split_off_moves(selected_moves)
                all_new_pickings |= new_picking

            picking.update_available_percent()
            all_new_pickings |= picking
        

        all_new_pickings.update_available_percent()
        if all_new_pickings:
            return {
                'name': 'Facturas Divididas',
                'type': 'ir.actions.act_window',
                'view_mode': 'tree,form',
                'res_model': 'stock.picking',
                'domain': [('id', 'in', all_new_pickings.ids)],
            }
        return False
    
    def action_print_remito(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/remito/auto/{self.id}',
            'target': 'new',
        }
    
    def action_print_remito2(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/backend/remito/pdf/{self.id}',
            'target': 'new',
        }
    
    def action_print_remito3(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/remito/auto2/{self.id}',
            'target': 'new',
        }
       
    def _prepare_remito_data(self, picking, proportion, company_id, type):
        partner = picking.partner_id

        lines = []
        total_bultos = 0
        total_unidades = 0
        date = picking.date_done
        date = date.strftime('%d-%m-%Y')

        if partner.type == 'contact':            
            partner_name = f"{partner.name}"
        else:            
            partner_name = f"{partner.parent_id.name}"
        

        partner_name = partner_name[:45]

        if type == 'b':
            partner_name = f"{partner_name}*"
            
        

        for move in picking.move_ids_without_package:
            qty = move.quantity_done * proportion

            # redeondeo unidades con decimal según blanco/negro el remito
            if qty % 1 != 0:
                if type == 'a':
                    qty = math.floor(qty) # redondeo para abajo
                if type == 'b':
                    qty = math.ceil(qty) # redondeo para arriba


            if qty > 0:
                uxb = move.product_packaging_id.qty if move.product_packaging_id else 1
                bultos = qty / uxb if uxb else 1
                lote = move.lot_ids[:1].name if move.lot_ids else ''
                lote = lote[:22]
                product_code = move.product_id.default_code
                product_description = f"{move.product_id.name}"
                product_description = product_description[:55]
                product_name = f"[{move.product_id.default_code}] {move.product_id.name}"
                product_name = product_name[:60]

                
                lines.append({
                    'bultos': bultos,
                    'code': product_code,
                    'description': product_description,
                    'nombre': product_name,
                    'lote': lote,
                    'unidades': qty,
                })

                total_bultos += bultos
                total_unidades += qty
        
        total_value = picking.declared_value
        if total_value == 0:
            total_value = False
        
        client_location = f"{partner.city}, {partner.state_id.name}"

        remito = {
            'date': date,
            'client': {
                'name': partner_name,
                'address': partner.street[:54] or '',
                'location': client_location[:54] or '',
                'cuit': partner.vat,
                'iva': partner.l10n_ar_afip_responsibility_type_id.name if partner.l10n_ar_afip_responsibility_type_id else '',
            },
            'origin': picking.origin or '',
            'picking_name': picking.name[:20] or '',
            'codigo_wms': picking.codigo_wms or '',
            'destination': {
                'name': f"{partner.property_delivery_carrier_id.name or ''}",
                'address': f"{partner.property_delivery_carrier_id.address or ''}",
            },
            'move_lines': lines,
            'total_bultos': picking.number_of_packages,
            'total_units': picking.packaging_qty,
            'total_value': total_value,
            'company_name': company_id.name,
        }

        return remito
    
    def _build_remito_pdf(self, picking, proportion, company_id, type):
        remito = self._prepare_remito_data(picking, proportion, company_id, type)
        coords = self._get_remito_template_coords(company_id)

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        y = 0

        def draw_header():
            # date
            c.setFont("Helvetica-Bold", 12)
            c.drawString(*coords['fecha'], remito['date'])

            # client
            c.setFont("Helvetica", 11)
            y = coords['cliente_y']
            c.drawString(*coords['cliente_nombre'], remito['client']['name'])
            c.drawString(*coords['cliente_dire'], remito['client']['address'])
            c.drawString(*coords['cliente_localidad'], remito['client']['location'])
            c.setFont("Helvetica", 10)
            c.drawString(*coords['iva'], f"{remito['client']['iva']}")
            c.drawString(*coords['cuit'], f"{remito['client']['cuit']}")

            # origin / picking
            y = coords['origen_y']
            c.drawString(400, y, f"Origen: {remito['origin']}")
            y -= 15
            c.drawString(400, y, remito['picking_name'])
            y -= 15
            c.drawString(400, y, remito['codigo_wms'])

            # delivery address
            y = coords['entrega_y']
            c.drawString(50, y, remito['destination']['name'])
            y -= 15
            c.drawString(50, y, remito['destination']['address'])
            y -= 15
            
            return y

        y = draw_header()
        y = coords['tabla_y']
       

        def draw_footer():
            y = coords['resumen_y']
            c.setFont("Helvetica-Bold", 10)
            c.drawString(160, y, f"Cantidad de Bultos: {remito['total_bultos']:.2f}")
            c.drawString(320, y, f"Cantidad UXB: {remito['total_units']:.2f}")
            y = coords['valor_y']
            if remito['total_value']:
                c.drawString(450, y, f"$ {remito['total_value']:,.2f}")
        
        for linea in remito['move_lines']:
            if company_id.id in (1, 2, 3):
                if y < 175:
                    draw_footer()
                    c.showPage()
                    draw_header()
                    y = coords['tabla_y']
            elif company_id.id == 4:
                if y < 135:
                    draw_footer()
                    c.showPage()
                    draw_header()
                    y = coords['tabla_y']

             
            c.setFont("Helvetica", 8)
            c.drawString(50, y, f"{linea['bultos']:.2f}")
            c.drawString(coords['producto_nombre_x'], y, linea['nombre'])
            c.drawString(390, y, linea['lote'])
            c.drawRightString(540, y, f"{int(linea['unidades'])}")
            y -= 15

        draw_footer()

        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
    
    def _build_remito_pdf2(self, picking, proportion, company_id, type):
        remito = self._prepare_remito_data(picking, proportion, company_id, type)
        rcoords = self.get_new_remito_coords()
        config_param = self.env['ir.config_parameter']
        left = int(config_param.sudo().get_param('remito_margen_left'))
        right = int(config_param.sudo().get_param('remito_margen_right'))
        top = int(config_param.sudo().get_param('remito_margen_top'))
        bottom = int(config_param.sudo().get_param('remito_margen_bottom'))

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)

        # ----------- FUNCIONES PARA HEADER Y TABLA -----------
        def draw_header():
            c.setLineWidth(1)
            container_x = int(config_param.sudo().get_param('container_x'))
            container_y = int(config_param.sudo().get_param('container_y'))
            container_width = right - left
            container_height = int(config_param.sudo().get_param('container_h'))
            c.roundRect(container_x, container_y, container_width, container_height, radius=10)

            c.setFont("Helvetica-Bold", 13)
            c.drawString(rcoords['fecha_x'], rcoords['fecha_y'], "FECHA: " + (remito.get('date', "")))
            c.setFont("Helvetica", 10)
            c.drawString(rcoords['cliente_x'], rcoords['cliente_y'], f"Cliente: {remito['client']['name']}")
            c.drawString(rcoords['direccion_x'], rcoords['direccion_y'], f"Dirección: {remito['client']['address']}")
            c.drawString(rcoords['localidad_x'], rcoords['localidad_y'], f"Localidad: {remito['client']['location']}")
            c.drawString(rcoords['iva_x'], rcoords['iva_y'], f"IVA: {remito['client']['iva']}")
            c.drawString(rcoords['cuit_x'], rcoords['cuit_y'], f"CUIT: {remito['client']['cuit']}")
            c.drawString(rcoords['transporte_x'], rcoords['transporte_y'], f"Transporte: {remito['destination']['name']}")
            c.drawString(rcoords['transporte2_x'], rcoords['transporte2_y'], f"{remito['destination']['address']}")
            c.drawString(rcoords['pedido_x'], rcoords['pedido_y'], f"Pedido: {remito['origin']}")
            c.drawString(rcoords['transferencia_x'], rcoords['transferencia_y'], f"TR: {remito['picking_name']}")
            c.drawString(rcoords['wms_x'], rcoords['wms_y'], f"WMS: {remito['codigo_wms']}")

        def draw_table_headers():
            tabla_top = top
            tabla_left = left
            tabla_right = right
            tabla_bottom = bottom
            col_bultos = left + 10
            col_codigo = left + 55
            col_producto = left + 100
            col_lote = left + 380
            col_unidades = right - 50

            c.setLineWidth(1)
            c.roundRect(tabla_left, tabla_bottom, tabla_right - tabla_left, tabla_top - tabla_bottom, radius=10)
            c.line(col_codigo-10, tabla_top, col_codigo-10, tabla_bottom)
            c.line(col_producto-9, tabla_top, col_producto-10, tabla_bottom)
            c.line(col_lote, tabla_top, col_lote, tabla_bottom)        
            c.line(col_unidades, tabla_top, col_unidades, tabla_bottom)

            c.setFont("Helvetica-Bold", 9)
            c.drawString(col_bultos -1, tabla_top - 15, "Bultos")
            c.drawString(col_codigo-1, tabla_top - 15, "Código")
            c.drawString(col_producto, tabla_top - 15, "Descripción")
            c.drawString(col_lote +10, tabla_top - 15, "Despacho")
            c.drawString(col_unidades+5, tabla_top - 15, "Unidades")
            c.line(tabla_left, tabla_top - 20, tabla_right, tabla_top - 20)
            return tabla_top, tabla_left, tabla_right, tabla_bottom, col_bultos, col_codigo, col_producto, col_lote, col_unidades

        def draw_footer():
            c.setFont("Helvetica-Bold", 10)
            c.drawString(left, bottom - 20, f"Cantidad de Bultos: {remito.get('total_bultos', 0):.2f}")
            c.drawString(left + 200, bottom - 20, f"Cantidad UXB: {remito.get('total_units', 0):.2f}")
            if remito.get('total_value'):
                c.drawString(right - 120, bottom - 20, f"Total: $ {remito['total_value']:,.2f}")

        # ----------- MAIN LOOP: MULTI-PÁGINA -----------
        max_rows_per_page = 32
        row_height = 13

        move_lines = remito['move_lines']
        num_lines = len(move_lines)
        line_idx = 0

        while line_idx < num_lines:
            draw_header()
            tabla_top, tabla_left, tabla_right, tabla_bottom, col_bultos, col_codigo, col_producto, col_lote, col_unidades = draw_table_headers()
            y = tabla_top - 35

            for row in range(max_rows_per_page):
                if line_idx >= num_lines or y < tabla_bottom + row_height:
                    break
                linea = move_lines[line_idx]
                c.setFont("Helvetica", 8)
                c.drawString(col_bultos+1, y, f"{linea['bultos']:.2f}")
                c.drawString(col_codigo, y, linea['code'])
                c.drawString(col_producto, y, linea['description'])
                c.drawString(col_lote +10, y, linea['lote'])
                c.drawRightString(col_unidades + 35, y, f"{int(linea['unidades'])}")
                y -= row_height
                line_idx += 1

            # FOOTER (al pie de cada página)
            draw_footer()
            if line_idx < num_lines:
                c.showPage()

        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
    
    def get_new_remito_coords(self):
        remito_coords = self.env['remito.coords'].search([], limit=1)

        if remito_coords:

            return {            
                'fecha_x': remito_coords.fecha_x,
                'fecha_y': remito_coords.fecha_y,
                'cliente_x': remito_coords.cliente_x,
                'cliente_y': remito_coords.cliente_y,                
                'direccion_x': remito_coords.direccion_x,
                'direccion_y': remito_coords.direccion_y,                
                'localidad_x': remito_coords.localidad_x,
                'localidad_y': remito_coords.localidad_y,                
                'iva_x': remito_coords.iva_x,
                'iva_y': remito_coords.iva_y,                
                'cuit_x': remito_coords.cuit_x,
                'cuit_y': remito_coords.cuit_y,                
                'tel_x': remito_coords.tel_x,
                'tel_y': remito_coords.tel_y,                
                'transporte_x': remito_coords.transporte_x,
                'transporte_y': remito_coords.transporte_y,            
                'transporte2_x': remito_coords.transporte2_x,
                'transporte2_y': remito_coords.transporte2_y,               
                'pedido_x': remito_coords.pedido_x,
                'pedido_y': remito_coords.pedido_y,
                'transferencia_x': remito_coords.transferencia_x,
                'transferencia_y': remito_coords.transferencia_y,
                'wms_x': remito_coords.wms_x,
                'wms_y': remito_coords.wms_y,
                'bultos_x': remito_coords.bultos_x,
                'bultos_y': remito_coords.bultos_y,
                'cod_x': remito_coords.cod_x,
                'cod_y': remito_coords.cod_y,
                'descripcion_x': remito_coords.descripcion_x,
                'descripcion_y': remito_coords.descripcion_y,
                'despacho_x': remito_coords.despacho_x,
                'despacho_y': remito_coords.despacho_y,
                'unidades_x': remito_coords.unidades_x,
                'unidades_y': remito_coords.unidades_y,
                'cantidad_bultos_x': remito_coords.cantidad_bultos_x,
                'cantidad_bultos_y': remito_coords.cantidad_bultos_y,
                'cantidad_paquetes_x': remito_coords.cantidad_paquetes_x,
                'cantidad_paquetes_y': remito_coords.cantidad_paquetes_y,
                'valor_declarado_x': remito_coords.valor_declarado_x,
                'valor_declarado_y': remito_coords.valor_declarado_y,
            }

    def _get_remito_template_coords(self, company_id):

        if company_id.id in (1, 2):
            return {
                'fecha': (430, 739),
                'cliente_nombre': (89, 644),
                'cliente_dire': (89, 632),
                'cliente_localidad': (89, 620),
                'cliente_y': 644,
                'origen_y': 645,
                'iva':(70, 600),
                'cuit':(300, 600),
                'entrega_y': 570,
                'tabla_y': 510,
                'producto_nombre_x': 100,
                'resumen_y': 150,
                'valor_y': 125,
            }
        elif company_id.id == 3:
            return {
                'fecha': (430, 720),
                'cliente_nombre': (97, 644),
                'cliente_dire': (97, 632),
                'cliente_localidad': (97, 620),
                'cliente_y': 644,
                'origen_y': 645,
                'iva':(70, 600),
                'cuit':(310, 600),
                'entrega_y': 570,
                'tabla_y': 510,
                'producto_nombre_x': 100,
                'resumen_y': 155,
                'valor_y': 125,
            }
        elif company_id.id == 4:
            return {
                'fecha': (410, 680),
                'cliente_nombre': (85, 602),
                'cliente_dire': (85, 590),
                'cliente_localidad': (85, 579),
                'cliente_y': 602,
                'origen_y': 602,
                'iva':(70, 560),
                'cuit':(300, 560),
                'entrega_y': 530,
                'producto_nombre_x': 88,
                'tabla_y': 475,
                'resumen_y': 115,
                'valor_y': 87,
            }
        else:
            return {
                'fecha': (430, 750),
                'cliente': (85, 644),
                'cliente_y': 700,
                'origen_y': 700,
                'iva':(70, 603),
                'cuit':(300, 603),
                'entrega_y': 630,
                'tabla_y': 500,
                'resumen_y': 150,
                'valor_y': 125,
            }
        
    def _get_type_proportion(self, type):
        type = str(type or '').strip().upper()

        proportions = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }
        return proportions.get(type, (1.0, 0.0))

    def get_pickings(self):
            wms_codes = ["D12024", "P2160", "P2159", "P2169", "D12000", "D12067", "D12001", "P2152", "P2241", "P2242", "P2243", "P2237", "P2239", "D12075", "P1996", "D11993", "D11994", "P2235", "P329", "P330", "P331", "P332", "P333", "P334", "P335","P336", "D10561", "P732", "P733", "P744", "P2211", "D12056", "D11143", "D11144", "D11142", "D11145", "D11146", "P905", "D11256", "P1222", "P1233", "P1234", "P1371", "P1515", "P1566", "D11483", "D11484", "P1684", "P1685","P1688", "P1689", "P1690", "P1691", "P1692", "P1693", "P1694", "P1657", "P1656", "D11527", "D11529", "D11509", "D11583", "P1699", "P1700", "P1701", "P1702", "P1705", "P1706", "P1709", "P1719", "D11693", "P1813", "P1814","D11876", "D11645", "D11644", "D11646", "P1768", "D11705", "D11704", "D11706", "P1891", "P1902", "P1903", "P1904", "P1905", "P1906", "P1888", "P1889", "P1890", "P1922", "D11751", "D11752", "D11681", "D11680", "P1948","P1949", "D11803", "D11802", "D11857", "D11858", "D11907", "D11908", "P2045", "D11894", "P2018", "P2031", "P2053", "P2054", "P2059", "P2060", "P1978", "P2015", "D11868", "P2005", "P1982", "P2013", "D11875", "D11874","P2052", "D11970", "D11927", "P2075", "P2074", "P2076", "D11951", "P2091", "P2092", "D11926", "D11935", "D11941", "P2119", "P2118", "P2122", "D11911", "D11913", "D11932", "D11933", "D12006", "D12039", "D11984","P2254", "D11991", "D11992", "P2153", "D12021", "D12022", "D12020", "D11980", "D11979", "D11978", "D11997", "P2252", "D11998", "P2158", "P2157", "D12007", "P2164", "D12014", "D12015", "D12027", "D12033", "P2140","P2165", "P2166", "P2167", "P2233", "P2182", "D12041", "P2207", "P2231", "D12062", "P2234", "D12066", "P2216", "P2238", "P2236", "D12057", "P2212", "P2208", "P2291", "D12099", "D12104", "D8892", "D8894", "D8896", "D8898", "D8900", "D8902", "D8893", "D8895", "D8897", "D8899", "D8901", "D8903"]

            pickings = self.env['stock.picking'].search([('codigo_wms', 'in', wms_codes)])
            
            result = []


            for p in pickings:
                if p.invoice_ids:
                    for i in p.invoice_ids:
                        result.append(f"{p.create_date};{p.partner_id.name};{p.name};{p.codigo_wms};{p.origin};{i.name};{i.invoice_date}")
                else:
                    result.append(f"{p.create_date};{p.partner_id.name};{p.name};{p.codigo_wms};{p.origin}")

            result2 = '\n'.join(result)

            raise UserError(result2)

class StockMoveInherit(models.Model):
    _inherit = "stock.move"

    product_available_percent = fields.Float(string='Porc Disponible', compute='_calculate_bultos', store=True, group_operator='avg')
    product_packaging_qty = fields.Float(string='Bultos', compute='_calculate_bultos', store=True)
    product_available_pkg_qty = fields.Float(string='Bultos Disponibles', compute='_calculate_bultos', store=True)

    license = fields.Char(string="Licencia", related='picking_id.carrier_tracking_ref', store=True)

    @api.depends('quantity_done', 'product_uom_qty')
    def _calculate_bultos(self):
        for record in self:
            if record.product_uom_qty > 0:
                record.product_available_percent = (record.quantity_done * 100) / record.product_uom_qty
            

class MergeDeliveriesInherit(models.TransientModel):
    _inherit = "merge.deliveries.wizard"

    def prepare_to_merge_deliveries(self):
        
        company_ids = self.picking_ids.mapped('company_id.id')

        if len(set(company_ids)) > 1:
            raise UserError(_('Merge is only allowed between deliveries of the same company'))

        return super().prepare_to_merge_deliveries()
    

class RemitoCoords(models.Model):
    _name = 'remito.coords'

    fecha_x = fields.Integer('Fecha X')
    fecha_y = fields.Integer('Fecha Y')

    cliente_x = fields.Integer('Cliente X')
    cliente_y = fields.Integer('Cliente Y')
    
    direccion_x = fields.Integer('Direccion X')
    direccion_y = fields.Integer('Direccion Y')
    
    localidad_x = fields.Integer('Localidad X')
    localidad_y = fields.Integer('Localidad Y')
    
    iva_x = fields.Integer('IVA X')
    iva_y = fields.Integer('IVA Y')
    
    cuit_x = fields.Integer('CUIT X')
    cuit_y = fields.Integer('CUIT X')
    
    tel_x = fields.Integer('Tel X')
    tel_y = fields.Integer('Tel Y')
    
    transporte_x = fields.Integer('Transporte X')
    transporte_y = fields.Integer('Transporte Y')
    
    transporte2_x = fields.Integer('TransporteAddress X')
    transporte2_y = fields.Integer('TransporteAddress Y')

    pedido_x = fields.Integer('Pedido X')
    pedido_y = fields.Integer('Pedido Y')

    transferencia_x = fields.Integer('Transferencia X')
    transferencia_y = fields.Integer('Transferencia Y')

    wms_x = fields.Integer('WMS X')
    wms_y = fields.Integer('WMS Y')

    bultos_x = fields.Integer('Bultos X')
    bultos_y = fields.Integer('Bultos Y')

    cod_x = fields.Integer('Codigo X')
    cod_y = fields.Integer('Codigo Y')

    descripcion_x = fields.Integer('Descripcion X')
    descripcion_y = fields.Integer('Descripcion Y')

    despacho_x = fields.Integer('Despacho X')
    despacho_y = fields.Integer('Despacho Y')

    unidades_x = fields.Integer('Unidades X')
    unidades_y = fields.Integer('Unidades Y')

    cantidad_bultos_x = fields.Integer('Cantidad Bultos X')
    cantidad_bultos_y = fields.Integer('Cantidad Bultos Y')

    cantidad_paquetes_x = fields.Integer('Cantidad Paquetes X')
    cantidad_paquetes_y = fields.Integer('Cantidad Paquetes Y')

    valor_declarado_x = fields.Integer('Valor Declarado X')
    valor_declarado_y = fields.Integer('Valor Declarado Y')

class DeliveryCarrierInherit(models.Model):
    _inherit = "delivery.carrier"

    address = fields.Char(string="Dirección")
    cuit = fields.Char(string="CUIT")
    
    #validar que el cuit sea unico debe salir validaterror
    @api.constrains('cuit')
    def _check_cuit_unique(self):
        for record in self:
            if record.cuit:
                if self.search_count([('cuit', '=', record.cuit)]) > 1:
                    raise ValidationError(_('El CUIT debe ser único por Transporte.'))

class StockSequenceWesend(models.Model):
    _name = "stock.sequence.wesend"

    name = fields.Char(string="Nombre", required=True)
    picking_id = fields.Many2one('stock.picking', string="Transferencia", required=True)
    sequence = fields.Integer(string="Secuencia", required=True)
    sequence_id = fields.Many2one('ir.sequence', string="Secuencia", required=True)