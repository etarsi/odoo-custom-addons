from odoo import models, fields, api
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime

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


    def enviar(self):
        res = super().enviar()
        for record in self:
            record.wms_date = fields.Date.today()

        return res

    def ajustar_fecha(self):
        for record in self:
            record.wms_date = fields.Date.today()

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
    
    def print_remito(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/remito/auto/{self.id}',
            'target': 'new',
        }
    
    def _prepare_remito_data(self, picking, proportion, company_id):
        partner = picking.partner_id

        lineas = []
        total_bultos = 0
        total_unidades = 0
        date = picking.date_done
        date = date.strftime('%d-%m-%Y')

        for move in picking.move_ids_without_package:
            qty = move.quantity_done * proportion
            uxb = move.product_packaging_id.qty if move.product_packaging_id else 1
            bultos = qty / uxb if uxb else 1
            lote = move.lot_ids[:1].name if move.lot_ids else ''

            lineas.append({
                'bultos': bultos,
                'codigo': move.product_id.default_code or '',
                'nombre': move.product_id.name or '',
                'lote': lote,
                'unidades': qty,
            })

            total_bultos += bultos
            total_unidades += qty

        remito = {
            'date': date,
            'client': {
                'name': partner.name,
                'address': partner.street,
                'city': partner.city,
                'cuit': partner.vat,
                'iva': partner.l10n_ar_afip_responsibility_type_id.name if partner.l10n_ar_afip_responsibility_type_id else '',
            },
            'origin': picking.origin or '',
            'picking_name': picking.name or '',
            'destinaton': {
                'name': partner.name,
                'address': f"{partner.street or ''}, {partner.zip or ''} {partner.city or ''}",
            },
            'move_lines': lineas,
            'total_bultos': picking.number_of_packages,
            'total_units': picking.packaging_qty,
            'total_value': sum(move.product_id.list_price * move.quantity_done for move in picking.move_ids_without_package),
            'company_name': company_id.name,
        }

        return remito
    
    def _build_remito_pdf(self, picking, proportion, company_id):
        remito = self._prepare_remito_data(picking, proportion, company_id)
        coords = self._get_remito_template_coords(company_id)

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Fecha
        c.setFont("Helvetica", 10)
        c.drawString(*coords['fecha'], remito['date'])

        # Cliente
        y = coords['cliente_y']
        c.drawString(40, y, remito['client']['name'])
        y -= 15
        c.drawString(40, y, remito['client']['address'])
        y -= 15
        c.drawString(40, y, remito['client']['city'])
        y -= 15
        c.drawString(40, y, f"CUIT: {remito['client']['cuit']}")
        y -= 15
        c.drawString(40, y, f"Condición de IVA: {remito['client']['iva']}")

        # Origen / Picking
        y = coords['origen_y']
        c.drawString(40, y, f"Origen: {remito['origin']}")
        c.drawString(250, y, remito['picking_name'])

        # Dirección de entrega
        y = coords['entrega_y']
        c.drawString(40, y, remito['destination']['name'])
        y -= 15
        c.drawString(40, y, remito['destination']['address'])

        # Tabla productos
        y = coords['tabla_y']
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, "Bultos")
        c.drawString(90, y, "Producto")
        c.drawString(360, y, "Lote")
        c.drawString(500, y, "Unidades")
        y -= 15
        c.setFont("Helvetica", 10)

        for linea in remito['move_lines']:
            if y < 100:
                c.showPage()
                y = height - 100

            c.drawString(40, y, f"{linea['bultos']:.2f}")
            c.drawString(90, y, f"[{linea['codigo']}] {linea['nombre']}")
            c.drawString(360, y, linea['lote'])
            c.drawString(500, y, f"{linea['unidades']:.2f}")
            y -= 15

        # Resumen
        y = coords['resumen_y']
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, f"Cantidad de Bultos: {remito['total_bultos']:.2f}")
        y -= 15
        c.drawString(40, y, f"Cantidad UXB: {remito['total_units']:.2f}")
        y -= 15
        c.drawString(40, y, f"$ {remito['total_value']:,.2f}")

        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    
    def _get_remito_template_coords(self, company_id):

        if company_id.id == 2:
            return {
                'fecha': (480, 790),
                'cliente_y': 740,
                'origen_y': 655,
                'entrega_y': 620,
                'tabla_y': 580,
                'resumen_y': 100,
            }
        elif company_id.id == 3:
            return {
                'fecha': (470, 780),
                'cliente_y': 730,
                'origen_y': 650,
                'entrega_y': 615,
                'tabla_y': 570,
                'resumen_y': 90,
            }
        elif company_id.id == 4:
            return {
                'fecha': (460, 785),
                'cliente_y': 735,
                'origen_y': 660,
                'entrega_y': 625,
                'tabla_y': 585,
                'resumen_y': 95,
            }
        else:
            # Valores por defecto
            return {
                'fecha': (480, 790),
                'cliente_y': 740,
                'origen_y': 655,
                'entrega_y': 620,
                'tabla_y': 580,
                'resumen_y': 100,
            }
