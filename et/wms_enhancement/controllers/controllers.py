from odoo import http
from odoo.http import request
from odoo.tools import file_open
from odoo.tools.misc import xlsxwriter
from odoo.http import content_disposition
from odoo.exceptions import UserError
from odoo.tools.pdf import merge_pdf 
import logging
_logger = logging.getLogger(__name__)

class WMSTaskController(http.Controller):
    

    @http.route('/nremito/auto/<int:task_id>', type='http', auth='user', website=False)
    def new_remito_auto(self, task_id, **kwargs):
        task = request.env['wms.task'].browse(task_id)
        if not task.exists():
            return request.not_found()

        tipo = task.invoicing_type
        blanco_pct, negro_pct = self._get_type_proportion(tipo)

        pdf_parts = []

        # --- Remito A (blanco) ---
        if blanco_pct > 0:
            company_a = task.company_id
            # si tenés alguna lógica especial para A, aplicala acá
            pdf_a = task._build_remito_pdf(task, blanco_pct, company_a, 'a')
            if pdf_a:
                pdf_parts.append(pdf_a)

        # --- Remito B (negro) ---
        if negro_pct > 0:
            # tu excepción para TIPO 3
            company_b = request.env['res.company'].browse(1) if tipo == 'TIPO 3' else task.company_id
            pdf_b = task._build_remito_pdf(task, negro_pct, company_b, 'b')
            if pdf_b:
                pdf_parts.append(pdf_b)

        if not pdf_parts:
            return request.make_response("Nada para imprimir", headers=[('Content-Type', 'text/plain')])

        pdf_bytes = pdf_parts[0] if len(pdf_parts) == 1 else merge_pdf(pdf_parts)

        filename = 'REM_%s.pdf' % (task.name or str(task_id)).replace('/', '-')
        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(pdf_bytes))),
            ('Content-Disposition', 'inline; filename="%s"' % filename),
            # Opcional: evitar caches raros del navegador
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
            ('Pragma', 'no-cache'),
        ]
        return request.make_response(pdf_bytes, headers=headers)
       
    
    def _get_type_proportion(self, type):
        type = str(type or '').strip().upper()

        proportions = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }
        return proportions.get(type, (1.0, 0.0))
    

    @http.route('/newremito/auto/<int:task_id>', type='http', auth='user')
    def new_remito_auto(self, task_id, **kwargs):
        task = request.env['wms.task'].browse(task_id)
        if not task.exists():
            return request.not_found()

        tipo = task.invoicing_type
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
            html += f"abrir('/nremito/a/{task.id}', 50);"
        if negro_pct > 0:
            html += f"abrir('/nremito/b/{task.id}', 200);"

        html += """
        </script>
        <p>Puede cerrar esta pagina.</p>
        </body></html>
        """

        return request.make_response(html, headers=[('Content-Type', 'text/html')])
    

    @http.route('/nremito/a/<int:task_id>', type='http', auth='user')
    def new_remito_a(self, task_id, **kwargs):
        task = request.env['wms.task'].browse(task_id)
        if not task.exists():
            return request.not_found()

        type = 'a'
        tipo = task.invoicing_type
        proportion, _ = self._get_type_proportion(tipo)

        if proportion == 0:
            return request.not_found()

        company_id = task.company_id

        pdf = task._build_remito_pdf(task, proportion, company_id, type)

        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="REM_{task.name.replace("/", "-")}.pdf"')
            ]
        )

    @http.route('/nremito/b/<int:task_id>', type='http', auth='user')
    def new_remito_b(self, task_id, **kwargs):
        task = request.env['wms.task'].browse(task_id)
        if not task.exists():
            return request.not_found()

        type = 'b'
        tipo = task.invoicing_type
        _, proportion = self._get_type_proportion(tipo)

        if proportion == 0:
            return request.not_found()
        
        if tipo == 'TIPO 3':
            company_id = request.env['res.company'].browse(1)
        else:
            company_id = task.company_id

        pdf = task._build_remito_pdf(task, proportion, company_id, type)
        
        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'inline; filename="REM_{task.name.replace("/", "-")}.pdf"')
            ]
        )