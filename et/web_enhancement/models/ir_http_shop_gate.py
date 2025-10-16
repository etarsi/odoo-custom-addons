import time
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

        gate_ok = request.session.get('shop_gate_ok')
        gate_until = request.session.get('shop_gate_until')  # puede ser None
        now = time.time()

        # Si venció el TTL, “cierra” la puerta
        if gate_until and now > gate_until:
            request.session.pop('shop_gate_ok', None)
            request.session.pop('shop_gate_until', None)
            gate_ok = False

        if path.startswith('/shop') \
           and not any(path.startswith(p) for p in ALLOW_PATHS) \
           and not gate_ok:
            return request.redirect('/shop/gate')

        return super()._dispatch()
