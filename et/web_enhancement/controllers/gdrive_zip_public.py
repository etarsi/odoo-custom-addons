# controllers/gdrive_zip_xmlrpc.py
# -*- coding: utf-8 -*-
import xmlrpc.client, logging, socket, urllib.parse
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

# Opcional: timeout global (simple)
socket.setdefaulttimeout(15)

class GDriveZipXMLRPC(http.Controller):

    @http.route('/gdrive/zip/public_xmlrpc', type='json', auth='public', methods=['POST'], csrf=False)
    def gdrive_zip_public_xmlrpc(self, **kw):
        body = request.jsonrequest or {}
        pid = int(body.get('product_id') or kw.get('product_id') or 0)
        if not pid:
            return {"ok": False, "message": _("Parámetro 'product_id' faltante.")}
        # Parámetros de conexión XML-RPC (deberían estar en Configuración)
        URL  = "https://one.sebigus.com.ar"
        DB   = "one"
        USER = "rrhh@sebigus.com.ar"
        KEY  = "123"
        # ¿Apunta al MISMO Odoo/DB? Usar ORM directamente: más rápido y sin red.
        same_host = URL and (urllib.parse.urlparse(URL).netloc == urllib.parse.urlparse(request.httprequest.host_url).netloc)
        if same_host:
            try:
                # Ejecutar en sudo (o con un usuario técnico si querés contexto)
                tmpl = request.env['product.template'].sudo().browse(pid).exists()
                res = tmpl.action_zip_by_default_code_from_main_folder()
                url = (isinstance(res, dict) and res.get('url')) or None
                if url:
                    return {"ok": True, "url": url}
                return {"ok": False, "message": _("Operación finalizada sin URL directa.")}
            except Exception as e:
                _logger.exception("Error ORM directo en public_xmlrpc: %s", e)
        if not (URL and DB and USER and KEY):
            return {"ok": False, "message": _("Credenciales/URL XML-RPC no configuradas.")}

        try:
            common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common", allow_none=True)
            uid = common.authenticate(DB, USER, KEY, {})
            if not uid:
                return {"ok": False, "message": _("Autenticación fallida.")}

            models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)

            # Ejecuta tu método en el otro lado (o en este mismo Odoo si URL apunta acá)
            res = models.execute_kw(DB, uid, KEY, 'product.template', 'download_image_product', [[pid]], {})

            # Esperamos un ir.actions.act_url
            if isinstance(res, dict) and res.get('type') == 'ir.actions.act_url' and res.get('url'):
                return {"ok": True, "url": res['url']}

            return {"ok": False, "message": _("Operación finalizada sin URL directa.")}
        except Exception as e:
            _logger.info("Error XML-RPC: %s", e)
            return {"ok": False, "message": _("Error inesperado comunicando con Odoo.")}
