# controllers/gdrive_zip_xmlrpc.py
# -*- coding: utf-8 -*-
import xmlrpc.client, logging, socket
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
        URL  = "https://one.sebigus.com.ar/"
        DB   = "one"
        USER = "rrhh@sebigus.com.ar"
        KEY  = "123"

        if not (URL and DB and USER and KEY):
            return {"ok": False, "message": _("Credenciales/URL XML-RPC no configuradas.")}

        try:
            common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common", allow_none=True)
            uid = common.authenticate(DB, USER, KEY, {})
            if not uid:
                return {"ok": False, "message": _("Autenticación fallida.")}

            models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)

            # Ejecuta tu método en el otro lado (o en este mismo Odoo si URL apunta acá)
            res = models.execute_kw(
                DB, uid, KEY,
                'product.template',
                'action_zip_by_default_code_from_main_folder',
                [[pid]],  # args
                {}        # kwargs
            )

            # Esperamos un ir.actions.act_url
            if isinstance(res, dict) and res.get('type') == 'ir.actions.act_url' and res.get('url'):
                return {"ok": True, "url": res['url']}

            return {"ok": False, "message": _("Operación finalizada sin URL directa.")}

        except Exception as e:
            _logger.exception("Error XML-RPC")
            return {"ok": False, "message": _("Error inesperado comunicando con Odoo.")}
