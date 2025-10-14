# controllers/gdrive_zip_public.py
from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class GDriveZipPublicController(http.Controller):

    @http.route('/gdrive/zip/public', type='json', auth='public', methods=['POST'], csrf=False)
    def gdrive_zip_public(self, **kw):
        try:
            # fuentes posibles
            body = request.jsonrequest or {}
            params = (body.get('params') or {}) if isinstance(body, dict) else {}

            # tomar product_id del lugar que venga
            pid = kw.get('product_id') \
                  or body.get('product_id') \
                  or params.get('product_id')

            # log para depurar si aún no llega
            _logger.info("ZIP public payload kw=%s body=%s params=%s", kw, body, params)

            pid = int(pid or 0)
            if not pid:
                return {"ok": False, "message": _("Parámetro 'product_id' faltante.")}

            # ejecutar como sudo (tu método ya hace sudo, igual es seguro)
            tmpl = request.env['product.template'].sudo().browse(pid).exists()
            if not tmpl:
                return {"ok": False, "message": _("Producto no encontrado.")}

            res = tmpl.action_zip_by_default_code_from_main_folder()

            if isinstance(res, dict) and res.get('type') == 'ir.actions.act_url' and res.get('url'):
                return {"ok": True, "url": res['url']}

            return {"ok": False, "message": _("Operación finalizada sin URL directa.")}

        except UserError:
            return {"ok": False, "message": _("Se produjo un error al obtener las imágenes, por favor contáctese a soporte.")}
        except Exception:
            _logger.exception("Error inesperado en /gdrive/zip/public")
            return {"ok": False, "message": _("Error inesperado. Intente nuevamente.")}
