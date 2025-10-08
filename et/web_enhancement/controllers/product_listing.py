# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from werkzeug.utils import redirect
class ProductWebsiteController(http.Controller):

    @http.route(['/shop/product/<model("product.template"):product>/download-images-zip'],
                type='http', auth='public', website=True, methods=['GET'], csrf=False)
    def product_download_images_zip(self, product, **kw):
        """Genera el ZIP por default_code desde la carpeta principal (gdrive_folder_id) y lo descarga."""
        # Sólo permitir productos publicados en el website
        if not product.website_published:
            return request.not_found()

        # Llamamos a la acción del modelo (usa sudo para poder crear el attachment)
        try:
            action = product.sudo().action_zip_by_default_code_from_main_folder()
        except Exception as e:
            # Podés renderizar una página de error más linda si querés
            return request.render('website.404', {'error_message': str(e)})

        # La acción devuelve act_url a /web/content/<att_id>?download=true cuando es 1 producto
        if isinstance(action, dict) and action.get('type') == 'ir.actions.act_url' and action.get('url'):
            # Redirigimos a la URL de descarga
            return redirect(action['url'])

        # Si por alguna razón devolvió listado, redirigimos al último adjunto (caso raro en website)
        # o mostramos 404
        return request.not_found()
