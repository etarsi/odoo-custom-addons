# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class GDriveZipPublicController(http.Controller):

    @http.route('/gdrive/zip/public', type='json', auth='public', methods=['POST'], csrf=False)
    def gdrive_zip_public(self, **payload):
        """
        JSON IN:  { "product_id": 123 }
        JSON OUT: { "ok": true, "url": "/web/content/ID?..."}  o  { "ok": false, "message": "..." }
        """
        try:
            pid = int(payload.get('product_id') or 0)
            if not pid:
                return {"ok": False, "message": _("Parámetro 'product_id' faltante.")}

            # Usuario público -> ejecutamos con sudo (tu método ya hace sudo, igualamos por si cambia)
            env = request.env
            tmpl = env['product.template'].sudo().browse(pid).exists()
            if not tmpl:
                return {"ok": False, "message": _("Producto no encontrado.")}
            _logger.info("Iniciando acción ZIP público para producto ID %d (Código: %s)", tmpl.id, tmpl.default_code or '—')
            res = tmpl.action_zip_by_default_code_from_main_folder()
            _logger.info("Resultado acción ZIP público: %s", res)
            # Si hay URL directa, la devolvemos
            if isinstance(res, dict) and res.get('type') == 'ir.actions.act_url' and res.get('url'):
                return {"ok": True, "url": res['url']}

            # Si no hay URL (p. ej. varios adjuntos), devolvemos genérico
            return {
                "ok": False,
                "message": _(
                    "La operación finalizó, pero no hay URL directa de descarga. "
                    "Por favor, revise los adjuntos del producto en Odoo."
                ),
            }

        except UserError as ue:
            # Mensaje neutral para web
            _logger.info("UserError en ZIP público: %s", ue.name or str(ue))
            return {"ok": False, "message": _("Se produjo un error al obtener las imágenes, por favor contáctese a soporte.")}
        except Exception as ex:
            _logger.info("Error inesperado en ZIP público")
            return {"ok": False, "message": _("Error inesperado. Intente nuevamente.")}
