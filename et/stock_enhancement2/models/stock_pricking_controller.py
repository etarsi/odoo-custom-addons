from odoo import http
from odoo.http import request
from odoo.tools import file_open
from odoo.tools.misc import xlsxwriter
from odoo.http import content_disposition

class StockPickingController(http.Controller):

    @http.route('/remito/pdf/<int:picking_id>', type='http', auth='user')
    def descargar_remito_pdf(self, picking_id, **kwargs):
        picking = request.env['stock.picking'].browse(picking_id)
        if not picking.exists():
            return request.not_found()

        pdf_content = picking._build_remito_pdf()

        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', content_disposition(f"remito_{picking.name}.pdf"))
            ]
        )