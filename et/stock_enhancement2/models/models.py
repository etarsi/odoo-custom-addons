from odoo import models, fields, api
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError
import logging
import math

_logger = logging.getLogger(__name__)

class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    wms_date = fields.Date(string="Fecha WMS")
    has_rodado = fields.Boolean(string="Rodados", compute="_compute_has_rodado", store=True)
    available_pkg_qty = fields.Float(string='Bultos Disponibles' ,compute='sum_bultos', group_operator='sum', store=True)

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
            c.drawString(80, y, remito['client']['name'])
            y -= 10
            c.drawString(80, y, remito['client']['address'])
            y -= 10
            c.drawString(80, y, remito['client']['city'])
            y -= 20
            c.setFont("Helvetica", 10)
            c.drawString(60, y, f"{remito['client']['iva']}")
            c.drawString(300, y, f"{remito['client']['cuit']}")

            # origin / picking
            y = coords['origen_y']
            c.drawString(420, y, f"Origen: {remito['origin']}")
            y -= 15
            c.drawString(420, y, remito['picking_name'])
            y -= 15
            c.drawString(420, y, remito['codigo_wms'])

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
                c.drawString(150, y, f"Cantidad de Bultos: {remito['total_bultos']:.2f}")
                c.drawString(320, y, f"Cantidad UXB: {remito['total_units']:.2f}")
                y = coords['valor_y']
                c.drawString(450, y, f"$ {remito['total_value']:,.2f}")
        
        for linea in remito['move_lines']:
            if y < 100:
                draw_footer()
                c.showPage()
                draw_header()
                y = coords['tabla_y']
                y -= 15
            
            c.setFont("Helvetica", 8)
            c.drawString(50, y, f"{linea['bultos']:.2f}")
            c.drawString(85, y, linea['nombre'])
            c.drawString(390, y, linea['lote'])
            c.drawString(510, y, f"{linea['unidades']:.2f}")
            y -= 15

        draw_footer()

        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    
    def _get_remito_template_coords(self, company_id):

        if company_id.id in (1, 2):
            return {
                'fecha': (430, 730),
                'cliente_y': 650,
                'origen_y': 650,
                'entrega_y': 580,
                'tabla_y': 540,
                'resumen_y': 150, # ok
                'valor_y': 125, # ok
            }
        elif company_id.id == 3:
            return {
                'fecha': (420, 710),
                'cliente_y': 650,
                'origen_y': 650,
                'entrega_y': 580,
                'tabla_y': 540,
                'resumen_y': 150, # ok
                'valor_y': 125, # ok
            }
        elif company_id.id == 4:
            return {
                'fecha': (420, 635),
                'cliente_y': 640,
                'origen_y': 640,
                'entrega_y': 560,
                'tabla_y': 520,
                'resumen_y': 120,
                'valor_y': 105,
            }
        else:
            return {
                'fecha': (430, 750),
                'cliente_y': 700,
                'origen_y': 700,
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