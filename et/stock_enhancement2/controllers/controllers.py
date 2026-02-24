from odoo import http
from odoo.http import request
from odoo.tools import file_open
from odoo.tools.misc import xlsxwriter
from odoo.http import content_disposition
from odoo.exceptions import UserError
from odoo.tools.pdf import merge_pdf 
import logging
_logger = logging.getLogger(__name__)

class StockPickingController(http.Controller):

    #comentar todo este controller 
    #@http.route('/remito/auto/<int:picking_id>', type='http', auth='user')
    #def remito_auto(self, picking_id, **kwargs):
    #    picking = request.env['stock.picking'].browse(picking_id)
    #    if not picking.exists():
    #        return request.not_found()

    #    tipo = str(picking.x_order_type.name or '').strip().upper()
    #    blanco_pct, negro_pct = self._get_type_proportion(tipo)

    #    html = """
    #    <html><head><title>Generando remitos...</title></head>
    #    <body>
    #   <script>
    #       function abrir(url, delay) {
    #           setTimeout(function() {
    #               window.open(url, '_blank');
    #           }, delay);
    #       }
    #   """
    #   if blanco_pct > 0:
    #        html += f"abrir('/remito/a/{picking.id}', 50);"
    #    if negro_pct > 0:
    #        html += f"abrir('/remito/b/{picking.id}', 200);"

    #    html += """
    #    </script>
    #    <p>Puede cerrar esta pagina.</p>
    #    </body></html>
    #    """
    #    return request.make_response(html, headers=[('Content-Type', 'text/html')])

    @http.route('/rem/auto/<int:picking_id>', type='http', auth='user', website=False)
    def remito_auto(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        tipo = str(picking.x_order_type.name or '').strip().upper()
        blanco_pct, negro_pct = self._get_type_proportion(tipo)

        pdf_parts = []

        # --- Remito A (blanco) ---
        if blanco_pct > 0:
            company_a = picking.company_id
            # si tenés alguna lógica especial para A, aplicala acá
            pdf_a = picking._build_remito_pdf2(picking, blanco_pct, company_a, 'a')
            if pdf_a:
                pdf_parts.append(pdf_a)

        # --- Remito B (negro) ---
        if negro_pct > 0:
            # tu excepción para TIPO 3
            company_b = request.env['res.company'].browse(1) if tipo == 'TIPO 3' else picking.company_id
            pdf_b = picking._build_remito_pdf2(picking, negro_pct, company_b, 'b')
            if pdf_b:
                pdf_parts.append(pdf_b)

        if not pdf_parts:
            return request.make_response("Nada para imprimir", headers=[('Content-Type', 'text/plain')])

        pdf_bytes = pdf_parts[0] if len(pdf_parts) == 1 else merge_pdf(pdf_parts)

        filename = 'REM_%s.pdf' % (picking.name or str(picking_id)).replace('/', '-')
        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(pdf_bytes))),
            ('Content-Disposition', 'inline; filename="%s"' % filename),
            # Opcional: evitar caches raros del navegador
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
            ('Pragma', 'no-cache'),
        ]
        return request.make_response(pdf_bytes, headers=headers)
    

    @http.route('/backend/remito/pdf/<int:picking_id>', type='http', auth='user', website=False)
    def remito_pdf(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        
        company_id = picking.company_id
        type = 'a'
        if company_id.id == 1:
            type = 'b'

        proportion = 1.0

        pdf = picking._build_remito_pdf2(picking, proportion, company_id, type)

        # if company_id.id == 4:
        #     pdf = picking._build_remito_pdf(picking, proportion, company_id, type)

        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="REM_{picking.name.replace("/", "-")}.pdf"')
            ]
        )   
    
    
    @http.route('/remito/a/<int:picking_id>', type='http', auth='user')
    def remito_a(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        type = 'a'
        tipo = picking.x_order_type.name
        proportion, _ = self._get_type_proportion(tipo)

        if proportion == 0:
            return request.not_found()

        company_id = picking.company_id

        pdf = picking._build_remito_pdf2(picking, proportion, company_id, type)

        # if company_id.id == 4:
        #     pdf = picking._build_remito_pdf(picking, proportion, company_id, type)

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

        type = 'b'
        tipo = picking.x_order_type.name
        _, proportion = self._get_type_proportion(tipo)

        if proportion == 0:
            return request.not_found()
        
        if tipo == 'TIPO 3':
            company_id = request.env['res.company'].browse(1)
        else:
            company_id = picking.company_id

        pdf = picking._build_remito_pdf2(picking, proportion, company_id, type)

        # if company_id.id == 4:
        #     pdf = picking._build_remito_pdf(picking, proportion, company_id, type)
        
        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="REM_{picking.name.replace("/", "-")}.pdf"')
            ]
        )
    
    def _get_type_proportion(self, type):
        type = str(type or '').strip().upper()

        proportions = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }
        return proportions.get(type, (1.0, 0.0))
    



    # TEMPORAL

    @http.route('/remito/auto2/<int:picking_id>', type='http', auth='user')
    def remito_auto2(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        tipo = str(picking.x_order_type.name or '').strip().upper()
        blanco_pct, negro_pct = self._get_type_proportion(tipo)

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
            html += f"abrir('/remito/aa/{picking.id}', 50);"
        if negro_pct > 0:
            html += f"abrir('/remito/bb/{picking.id}', 200);"

        html += """
        </script>
        <p>Puede cerrar esta pagina.</p>
        </body></html>
        """

        return request.make_response(html, headers=[('Content-Type', 'text/html')])
    

    @http.route('/remito/aa/<int:picking_id>', type='http', auth='user')
    def remito_aa(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        type = 'a'
        tipo = picking.x_order_type.name
        proportion, _ = self._get_type_proportion(tipo)

        if proportion == 0:
            return request.not_found()

        company_id = picking.company_id

        pdf = picking._build_remito_pdf2(picking, proportion, company_id, type)

        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="REM_{picking.name.replace("/", "-")}.pdf"')
            ]
        )

    @http.route('/remito/bb/<int:picking_id>', type='http', auth='user')
    def remito_bb(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        type = 'b'
        tipo = picking.x_order_type.name
        _, proportion = self._get_type_proportion(tipo)

        if proportion == 0:
            return request.not_found()
        
        if tipo == 'TIPO 3':
            company_id = request.env['res.company'].browse(1)
        else:
            company_id = picking.company_id

        pdf = picking._build_remito_pdf2(picking, proportion, company_id, type)
        
        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="REM_{picking.name.replace("/", "-")}.pdf"')
            ]
        )