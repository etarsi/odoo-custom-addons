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
    

    @http.route('/remito/auto/<int:task_id>', type='http', auth='user', website=False)
    def remito_auto(self, task_id, **kwargs):
        task = request.env['wms.task'].browse(task_id)
        if not task.exists():
            return request.not_found()

        tipo = str(task.invoicing_type or '').strip().upper()
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