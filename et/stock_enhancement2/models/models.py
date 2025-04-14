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
    
    
    
    def _build_remito_pdf(self, movimientos, nombre_compania, titulo="Remito"):
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 40

        # Título y compañía
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, f"{titulo} - {nombre_compania}")
        y -= 30

        total_bultos = 0
        total_unidades = 0

        for mov in movimientos:
            if y < 100:
                c.showPage()
                y = height - 100

            producto = mov['product']
            qty = mov['qty']
            bultos = mov['bultos']
            lote = mov['lote']

            total_bultos += bultos
            total_unidades += qty

            c.setFont("Helvetica", 10)
            c.drawString(40, y, f"{bultos:.2f}")
            c.drawString(90, y, f"[{producto.default_code}] {producto.name}")
            c.drawString(360, y, lote)
            c.drawString(500, y, f"{qty:.2f}")
            y -= 15

        # Resumen
        y -= 20
        c.drawString(40, y, f"Cantidad de Bultos: {total_bultos:.0f}")
        y -= 15
        c.drawString(40, y, f"Cantidad UXB: {total_unidades:.2f}")

        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
    
    def action_descargar_remitos_auto(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/remito/auto/{self.id}',
            'target': 'self',
        }