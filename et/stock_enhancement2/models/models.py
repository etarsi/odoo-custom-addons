from odoo import models, fields, api
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError, AccessError
import logging
import math
import requests
from itertools import groupby

_logger = logging.getLogger(__name__)

class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    wms_date = fields.Date(string="Fecha WMS")
    has_rodado = fields.Boolean(string="Rodados", compute="_compute_has_rodado", store=True)
    has_toys = fields.Boolean(string="Juguetes", compute="_compute_has_toys", store=True)
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
            

        return res

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
        company_negra = self.env['res.company'].browse(1)  # Producción B (ajustar si cambia)

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
                blanco_vals['tax_ids'] = [(6, 0, move.product_id.taxes_id.filtered(
                    lambda t: t.company_id.id == company_blanca.id).ids)]
                invoice_lines_blanco.append((0, 0, blanco_vals))

            if proportion_negro > 0:
                negro_vals = base_vals.copy()
                negro_vals['quantity'] = qty_negro
                negro_vals['price_unit'] *= 1.21
                negro_vals['tax_ids'] = [(6, 0, move.product_id.taxes_id.filtered(
                    lambda t: t.company_id.id == company_negra.id).ids)]
                invoice_lines_negro.append((0, 0, negro_vals))

            sequence += 1

        invoices = self.env['account.move']

        # Crear factura blanca
        if invoice_lines_blanco:
            vals_blanco = self._prepare_invoice_base_vals(company_blanca)
            vals_blanco['invoice_line_ids'] = invoice_lines_blanco
            invoices += self.env['account.move'].create(vals_blanco)

        # Crear factura negra
        if invoice_lines_negro:
            vals_negro = self._prepare_invoice_base_vals(company_negra)
            vals_negro['invoice_line_ids'] = invoice_lines_negro

            # Asignar journal correcto
            journal = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', company_negra.id)
            ], limit=1)
            if not journal:
                raise UserError("No se encontró un diario de ventas para Producción B.")
            vals_negro['journal_id'] = journal.id

            # Limpiar partner_bank si no es válido
            if vals_negro.get('partner_bank_id'):
                bank = self.env['res.partner.bank'].browse(vals_negro['partner_bank_id'])
                if bank.company_id and bank.company_id != company_negra:
                    vals_negro['partner_bank_id'] = False

            invoices += self.env['account.move'].create(vals_negro)

        # Relacionar con la transferencia
        invoices.write({
            'invoice_origin': self.origin or self.name,
        })

        self.invoice_ids = [(6, 0, invoices.ids)]

        for move in self.move_ids_without_package.filtered(lambda m: m.sale_line_id):
            move.sale_line_id.qty_invoiced += move.quantity_done
            move.invoice_state = 'invoiced'

        return {
            'name': "Facturas generadas",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', invoices.ids)],
        }
    
    def action_create_invoice_from_picking2(self):
        self.ensure_one()

        SaleOrder = self.sale_id
        if not SaleOrder:
            raise UserError("La transferencia no está vinculada a ningún pedido de venta.")

        proportion = 1.0

        company_id = self.company_id

        invoice_lines = []
        sequence = 1

        for move in self.move_ids_without_package:
            base_vals = move.sale_line_id._prepare_invoice_line(sequence=sequence)

            if proportion > 0:
                invoice_vals = base_vals.copy()
                invoice_vals['quantity'] = move.quantity_done * proportion
                invoice_vals['tax_ids'] = [(6, 0, move.product_id.taxes_id.filtered(
                    lambda t: t.company_id.id == company_id.id).ids)]
                invoice_lines.append((0, 0, invoice_vals))

                if company_id.id == 1:
                    invoice_vals['tax_ids'] = False
                    invoice_lines['price_unit'] *= 1.21

                    # # Asignar journal correcto
                    # journal = self.env['account.journal'].search([
                    #     ('type', '=', 'sale'),
                    #     ('company_id', '=', company_id.id)
                    # ], limit=1)
                    # if not journal:
                    #     raise UserError("No se encontró un diario de ventas para Producción B.")
                    # vals_blanco['journal_id'] = journal.id

                    # # Limpiar partner_bank si no es válido
                    # if vals_blanco.get('partner_bank_id'):
                    #     bank = self.env['res.partner.bank'].browse(vals_blanco['partner_bank_id'])
                    #     if bank.company_id and bank.company_id != company_id:
                    #         vals_blanco['partner_bank_id'] = False

            sequence += 1

        invoices = self.env['account.move']

        # Crear factura
        if invoice_lines:
            vals_invoice = self._prepare_invoice_base_vals(company_id)
            vals_invoice['invoice_line_ids'] = invoice_lines
            invoices += self.env['account.move'].create(vals_invoice)


        # Relacionar con la transferencia
        invoices.write({
            'invoice_origin': self.origin or self.name,
        })

        self.invoice_ids = [(6, 0, invoices.ids)]

        for move in self.move_ids_without_package.filtered(lambda m: m.sale_line_id):
            move.sale_line_id.qty_invoiced += move.quantity_done
            move.state = 'invoiced'

        return {
            'name': "Facturas generadas",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', invoices.ids)],
        }

    def _prepare_invoice_base_vals(self, company):
        partner = self.partner_id
        return {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.context_today(self),
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'invoice_user_id': self.env.user.id,
            'invoice_origin': self.origin or self.name,
            'payment_reference': self.name,
            'invoice_payment_term_id': partner.property_payment_term_id.id,
            'partner_bank_id': partner.bank_ids.filtered(lambda b: b.company_id == company)[:1].id,
            'fiscal_position_id': partner.property_account_position_id.id,
        }



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


    # def enviar(self):
    #     res = super().enviar()
    #     for record in self:
    #         record.wms_date = fields.Date.today()

    #     return res

    # def ajustar_fecha(self):
    #     for record in self:
    #         record.wms_date = fields.Date.today()

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
        for picking in self:
            selected_moves = self.env['stock.move']
            line_count = 0
            bulto_count = 0

            for move in picking.move_ids_without_package:
                if move.product_available_percent == 100:
                    if line_count > 24 or bulto_count >= 15:
                        break
                    
                    bulto_qty = bulto_count + move.product_packaging_qty
                    if bulto_qty <= 20:      
                        line_count += 1
                        bulto_count += move.product_packaging_qty
                        selected_moves |= move

            if selected_moves:
                return picking._split_off_moves(selected_moves)
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

            uxb = move.product_packaging_id.qty if move.product_packaging_id else 1
            bultos = qty / uxb if uxb else 1
            lote = move.lot_ids[:1].name if move.lot_ids else ''
            product_name = f"[{move.product_id.default_code}] {move.product_id.name}"
            product_name = product_name[:60]

            
            lines.append({
                'bultos': bultos,
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
                'address': partner.street or '',
                'location': client_location or '',
                'cuit': partner.vat,
                'iva': partner.l10n_ar_afip_responsibility_type_id.name if partner.l10n_ar_afip_responsibility_type_id else '',
            },
            'origin': picking.origin or '',
            'picking_name': picking.name or '',
            'codigo_wms': picking.codigo_wms or '',
            'destination': {
                'name': f"{partner.property_delivery_carrier_id.name or ''}",
                'address': f"{partner.property_delivery_carrier_id.partner_id.name or ''}",
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
        width, height = A4
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
            


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    def _create_invoices2(self, grouped=False, final=False, date=None):
        """
        Create the invoice associated to the SO.
        :param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
                        (partner_invoice_id, currency)
        :param final: if True, refunds will be generated if necessary
        :returns: list of created invoices
        """
        if not self.env['account.move'].check_access_rights('create', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                return self.env['account.move']

        # 1) Create invoices.
        invoice_vals_list = []
        invoice_item_sequence = 0 # Incremental sequencing to keep the lines order on the invoice.
        for order in self:
            order = order.with_company(order.company_id)
            current_section_vals = None
            down_payments = order.env['sale.order.line']

            invoice_vals = order._prepare_invoice()
            invoiceable_lines = order._get_invoiceable_lines(final)

            if not any(not line.display_type for line in invoiceable_lines):
                continue

            tipo = (order.condicion_m2m.name or '').upper().strip()
            proportion_blanco, proportion_negro = {
                'TIPO 1': (1.0, 0.0),
                'TIPO 2': (0.5, 0.5),
                'TIPO 3': (0.0, 1.0),
                'TIPO 4': (0.25, 0.75),
            }.get(tipo, (1.0, 0.0))

            company_negra = self.env['res.company'].browse(1)

            invoice_line_vals_blanco = []
            invoice_line_vals_negro = []

            for line in invoiceable_lines:
                base_vals = line._prepare_invoice_line(sequence=invoice_item_sequence)

                qty_total = base_vals['quantity']
                qty_blanco = math.floor(qty_total * proportion_blanco)
                qty_negro = qty_total - qty_blanco
                price_unit_negro = base_vals['price_unit'] * 1.21
                if tipo == 'TIPO 3':
                    price_unit_negro = base_vals['price_unit']
            

                impuestos_blancos = line.product_id.taxes_id.filtered(lambda t: t.company_id.id == order.company_id.id)

                if qty_blanco > 0:
                    invoice_line_vals_blanco.append((0, 0, {
                        **base_vals,
                        'quantity': qty_blanco,
                        'tax_ids': [(6, 0, impuestos_blancos.ids)],
                    }))

                if qty_negro > 0:
                    invoice_line_vals_negro.append((0, 0, {
                        **base_vals,
                        'quantity': qty_negro,
                        'price_unit': price_unit_negro,
                        'tax_ids': False,
                    }))

                invoice_item_sequence += 1

            # Crear invoice blanco si corresponde
            if invoice_line_vals_blanco:
                invoice_vals_blanco = order._prepare_invoice()
                invoice_vals_blanco['invoice_line_ids'] += invoice_line_vals_blanco
                invoice_vals_blanco['company_id'] = order.company_id.id
                invoice_vals_list.append(invoice_vals_blanco)

            # Crear invoice negro si corresponde
            if invoice_line_vals_negro:
                invoice_vals_negro = order._prepare_invoice()

                journal = self.env['account.journal'].browse(1)

                if not journal:
                    raise UserError("No se encontró un diario de ventas para la compañía negra.")
                
                invoice_vals_negro['company_id'] = company_negra.id
                invoice_vals_negro['journal_id'] = journal.id
                invoice_vals_negro['partner_bank_id'] = False
                invoice_vals_negro['invoice_line_ids'] += invoice_line_vals_negro
                invoice_vals_list.append(invoice_vals_negro)


        if not invoice_vals_list:
            raise self._nothing_to_invoice_error()

        # 2) Manage 'grouped' parameter: group by (partner_id, currency_id).
        if not grouped:
            new_invoice_vals_list = []
            invoice_grouping_keys = self._get_invoice_grouping_keys()
            invoice_vals_list = sorted(
                invoice_vals_list,
                key=lambda x: [
                    x.get(grouping_key) for grouping_key in invoice_grouping_keys
                ]
            )
            for grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: [x.get(grouping_key) for grouping_key in invoice_grouping_keys]):
                origins = set()
                payment_refs = set()
                refs = set()
                ref_invoice_vals = None
                for invoice_vals in invoices:
                    if not ref_invoice_vals:
                        ref_invoice_vals = invoice_vals
                    else:
                        ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                    origins.add(invoice_vals['invoice_origin'])
                    payment_refs.add(invoice_vals['payment_reference'])
                    refs.add(invoice_vals['ref'])
                ref_invoice_vals.update({
                    'ref': ', '.join(refs)[:2000],
                    'invoice_origin': ', '.join(origins),
                    'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
                })
                new_invoice_vals_list.append(ref_invoice_vals)
            invoice_vals_list = new_invoice_vals_list

        # 3) Create invoices.

        # As part of the invoice creation, we make sure the sequence of multiple SO do not interfere
        # in a single invoice. Example:
        # SO 1:
        # - Section A (sequence: 10)
        # - Product A (sequence: 11)
        # SO 2:
        # - Section B (sequence: 10)
        # - Product B (sequence: 11)
        #
        # If SO 1 & 2 are grouped in the same invoice, the result will be:
        # - Section A (sequence: 10)
        # - Section B (sequence: 10)
        # - Product A (sequence: 11)
        # - Product B (sequence: 11)
        #
        # Resequencing should be safe, however we resequence only if there are less invoices than
        # orders, meaning a grouping might have been done. This could also mean that only a part
        # of the selected SO are invoiceable, but resequencing in this case shouldn't be an issue.
        if len(invoice_vals_list) < len(self):
            SaleOrderLine = self.env['sale.order.line']
            for invoice in invoice_vals_list:
                sequence = 1
                for line in invoice['invoice_line_ids']:
                    line[2]['sequence'] = SaleOrderLine._get_invoice_line_sequence(new=sequence, old=line[2]['sequence'])
                    sequence += 1

        # Manage the creation of invoices in sudo because a salesperson must be able to generate an invoice from a
        # sale order without "billing" access rights. However, he should not be able to create an invoice from scratch.
        moves = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(invoice_vals_list)

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        if final:
            moves.sudo().filtered(lambda m: m.amount_total < 0).action_switch_invoice_into_refund_credit_note()
        for move in moves:
            move.message_post_with_view('mail.message_origin_link',
                values={'self': move, 'origin': move.line_ids.mapped('sale_line_ids.order_id')},
                subtype_id=self.env.ref('mail.mt_note').id
            )
        return moves


class SaleAdvancePaymentInvInherit(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def create_invoices2(self):
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))

        if self.advance_payment_method == 'delivered':
            sale_orders._create_invoices2(final=self.deduct_down_payments)
        else:
            # Create deposit product if necessary
            if not self.product_id:
                vals = self._prepare_deposit_product()
                self.product_id = self.env['product.product'].create(vals)
                self.env['ir.config_parameter'].sudo().set_param('sale.default_deposit_product_id', self.product_id.id)

            sale_line_obj = self.env['sale.order.line']
            for order in sale_orders:
                amount, name = self._get_advance_details(order)

                if self.product_id.invoice_policy != 'order':
                    raise UserError(_('The product used to invoice a down payment should have an invoice policy set to "Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'))
                if self.product_id.type != 'service':
                    raise UserError(_("The product used to invoice a down payment should be of type 'Service'. Please use another product or update this product."))
                taxes = self.product_id.taxes_id.filtered(lambda r: not order.company_id or r.company_id == order.company_id)
                tax_ids = order.fiscal_position_id.map_tax(taxes).ids
                analytic_tag_ids = []
                for line in order.order_line:
                    analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]

                so_line_values = self._prepare_so_line(order, analytic_tag_ids, tax_ids, amount)
                so_line = sale_line_obj.create(so_line_values)
                self._create_invoice(order, so_line, amount)
        if self._context.get('open_invoices', False):
            return sale_orders.action_view_invoice()
        return {'type': 'ir.actions.act_window_close'}