from odoo import http
from odoo.http import request
from odoo.tools import file_open
from odoo.tools.misc import xlsxwriter
from odoo.http import content_disposition

class StockPickingController(http.Controller):

    def _get_proporcion_tipo(self, tipo):
        proporciones = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }
        return proporciones.get(tipo, (1.0, 0.0))

    @http.route('/remito/blanco/<int:picking_id>', type='http', auth='user')
    def descargar_remito_blanco(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        tipo = picking.x_order_type or 'TIPO 1'
        blanco_pct, _ = self._get_proporcion_tipo(tipo)

        if blanco_pct == 0:
            return request.not_found()

        movimientos = []
        for move in picking.move_ids_without_package:
            qty = move.quantity_done * blanco_pct
            uxb = move.product_packaging_id.qty or 1
            movimientos.append({
                'product': move.product_id,
                'qty': qty,
                'bultos': qty / uxb,
                'lote': move.lot_ids[:1].name if move.lot_ids else '',
            })

        pdf = picking._build_remito_pdf(movimientos, picking.company_id.name, "Remito BLANCO")
        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', content_disposition(f"remito_blanco_{picking.name.replace('/', '-')}.pdf"))
            ]
        )

    @http.route('/remito/negro/<int:picking_id>', type='http', auth='user')
    def descargar_remito_negro(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        tipo = picking.x_order_type or 'TIPO 1'
        _, negro_pct = self._get_proporcion_tipo(tipo)

        if negro_pct == 0:
            return request.not_found()

        movimientos = []
        for move in picking.move_ids_without_package:
            qty = move.quantity_done * negro_pct
            uxb = move.product_packaging_id.qty or 1
            movimientos.append({
                'product': move.product_id,
                'qty': qty,
                'bultos': qty / uxb,
                'lote': move.lot_ids[:1].name if move.lot_ids else '',
            })

        pdf = picking._build_remito_pdf(movimientos, "Producción B", "Remito NEGRO")
        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', content_disposition(f"remito_negro_{picking.name.replace('/', '-')}.pdf"))
            ]
        )
    
    @http.route('/remito/auto/<int:picking_id>', type='http', auth='user')
    def remito_auto(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        tipo = picking.x_order_type or 'TIPO 1'
        blanco_pct, negro_pct = self._get_proporcion_tipo(tipo)

        urls = []
        if blanco_pct > 0:
            urls.append(f"/remito/blanco/{picking.id}")
        if negro_pct > 0:
            urls.append(f"/remito/negro/{picking.id}")

        html = "<html><body><script>"
        for url in urls:
            html += f"window.open('{url}', '_blank');"
        html += "</script><p>Generando remitos...</p></body></html>"

        return request.make_response(html, headers=[('Content-Type', 'text/html')])