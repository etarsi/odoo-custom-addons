# models/ir_http_shop_gate.py
from odoo import models
from odoo import http
from odoo.http import request

ALLOW_PATHS = (
    '/shop/gate',
    '/website/image',
    '/web/content',
    '/web/static',
)

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls):
        req = request.httprequest
        path = (req.path or '').rstrip('/') or '/'
        if path.startswith('/shop') \
           and not any(path.startswith(p) for p in ALLOW_PATHS) \
           and not request.session.get('shop_gate_ok'):
            # ✅ Odoo 15: redirect simple
            return request.redirect('/shop/gate')
        return super()._dispatch()
