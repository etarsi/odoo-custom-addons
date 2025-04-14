from odoo import http
from odoo.http import request
from odoo.tools import file_open
from odoo.tools.misc import xlsxwriter
from odoo.http import content_disposition
from odoo.exceptions import UserError
from odoo import _logger

class StockPickingController(http.Controller):
  
    @http.route('/remito/auto/<int:picking_id>', type='http', auth='user')
    def remito_auto(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()     

        type = picking.x_order_type
        blanco_pct, negro_pct = self._get_type_proportion(type)

        html = """
        <html><head><title>Generando remitos...</title></head>
        <body>
        <script>
            function abrir(url, delay) {
                setTimeout(function() {
                    window.open(url, '_blank');
                }, delay);
            }
        """
        if blanco_pct > 0:
            html += f"abrir('/remito/a/{picking.id}', 100);"
            
        if negro_pct > 0:
            html += f"abrir('/remito/b/{picking.id}', 500);"

        html += """
        </script>
        <p>Generando remitos...</p>
        </body></html>
        """

        return request.make_response(html, headers=[('Content-Type', 'text/html')])

    @http.route('/remito/a/<int:picking_id>', type='http', auth='user')
    def remito_a(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        tipo = picking.x_order_type
        proportion, _ = self._get_type_proportion(tipo)

        if proportion == 0:
            return request.not_found()

        company_id = picking.company_id

        pdf = picking._build_remito_pdf(picking, proportion, company_id)

        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="REM_{picking.name.replace("/", "-")}.pdf"')
            ]
        )

    @http.route('/remito/b/<int:picking_id>', type='http', auth='user')
    def remito_b(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        tipo = picking.x_order_type
        _, proportion = self._get_type_proportion(tipo)

        if proportion == 0:
            return request.not_found()
        
        company_id = self.env['res.company'].browse(1)

        pdf = picking._build_remito_pdf(picking, proportion, company_id)
        
        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="REM_{picking.name.replace("/", "-")}.pdf"')
            ]
        )
    
    def _get_type_proportion(self, type):
        type = str(type or '').strip().upper()
        _logger.info(f"type: {type}")

        proportions = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }
        return proportions.get(type, (1.0, 0.0))