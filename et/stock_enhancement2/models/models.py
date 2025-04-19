from odoo import models, fields, api
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError
import logging
import math
import requests

_logger = logging.getLogger(__name__)

class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    wms_date = fields.Date(string="Fecha WMS")
    has_rodado = fields.Boolean(string="Rodados", compute="_compute_has_rodado", store=True)
    available_pkg_qty = fields.Float(string='Bultos Disponibles' ,compute='sum_bultos', group_operator='sum', store=True)


    def update_available_percent(self):
        all_product_codes = set()

        for record in self:
            for move in record.move_ids_without_package:
                all_product_codes.add(move.product_id.default_code)

        stock_by_code = self._get_stock(list(all_product_codes))

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
                elif disponible == 0:
                    available_percent = 0
                    available_bultos = 0
                else:
                    available_percent = (disponible * 100) / move.product_uom_qty
                    available_bultos = move.product_uom_qty / move.product_packaging_id.qty

                move.product_available_percent = available_percent
                move.product_available_pkg_qty = available_bultos

            u_values = record.move_ids_without_package.mapped('product_available_percent')
            u_avg = (sum(u_values) / len(u_values)) if u_values else 0
            bultos = record.move_ids_without_package.mapped('product_available_pkg_qty')
            bultos_sum = sum(bultos)

            record.available_percent = round(u_avg, 2)
            record.available_pkg_qty = bultos_sum

                
    
    def _get_stock(self, product_codes):
        stock_by_code = {}
        headers = {}
        params = {}
        
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms-v2.url')
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        params = {'ArticuloCodigo': product_codes}        
        response = requests.get(f'{url}/v2/Stock/Tipo', headers=headers, params=params)

        if response.status_code == 200:
            products = response.json()
            stock_by_code = {p['codigo']: p['stock']['disponible'] for p in products}

            return stock_by_code or None

        elif response.status_code == 400:
            raise UserError('ERROR: 400 BAD REQUEST. Avise a su administrador de sistema.')
        elif response.status_code == 404:
            raise UserError('ERROR: 404 NOT FOUND. Avise a su administrador de sistema.')
        elif response.status_code == 500:
            raise UserError('ERROR: 500 INTERNAL SERVER ERROR. Avise a su administrador de sistema.')

    @api.depends('move_ids_without_package')
    def _compute_has_rodado(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.product_id.categ_id.parent_id.id == 320:
                    record.has_rodado = True


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
    
    def action_print_remito2(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/remito/auto/{self.id}',
            'target': 'new',
        }
    
    def _prepare_remito_data(self, picking, proportion, company_id, type):
        partner = picking.partner_id

        lines = []
        total_bultos = 0
        total_unidades = 0
        date = picking.date_done
        date = date.strftime('%d-%m-%Y')
        partner_name = partner.name

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
                # 'codigo': move.product_id.default_code or '',
                'nombre': product_name,
                'lote': lote,
                'unidades': qty,
            })

            total_bultos += bultos
            total_unidades += qty
        
        remito = {
            'date': date,
            'client': {
                'name': partner_name,
                'address': partner.street or '',
                'city': partner.city or '',
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
            'total_value': sum(move.product_id.list_price * move.quantity_done for move in picking.move_ids_without_package),
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
            c.drawString(*coords['cliente_localidad'], remito['client']['city'])
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
            c.drawRightString(540, y, f"{linea['unidades']:.2f}")
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