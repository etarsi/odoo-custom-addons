# -*- coding: utf-8 -*-
from odoo import models
from odoo import http
from odoo.http import request

ALLOW_PATHS = (
    '/shop/gate',          # la página del formulario
    '/website/image',      # imágenes
    '/web/content',        # adjuntos (descargas)
    '/web/static',         # assets
)

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls):
        req = request.httprequest
        path = (req.path or '').rstrip('/') or '/'
        # sólo interceptar /shop y subrutas (no tocar assets ni gate)
        if path.startswith('/shop') \
           and not any(path.startswith(p) for p in ALLOW_PATHS) \
           and not request.session.get('shop_gate_ok'):
            return http.redirect_with_hash('/shop/gate')
        return super()._dispatch()
