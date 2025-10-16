from odoo import http, _
import time
from odoo.http import request

class ShopGate(http.Controller):

    @http.route('/shop/gate', type='http', auth='public', website=True,  csrf=False, methods=['GET','POST'])
    def shop_gate(self, **post):
        msg = None
        if request.httprequest.method == 'POST':
            pwd_cfg = request.env['ir.config_parameter'].sudo().get_param('website.shop_gate_password') or ''
            if (post.get('password') or '') == pwd_cfg:
                request.session['shop_gate_ok'] = True
                request.session['shop_gate_until'] = time.time() + (5 * 60 * 60)  # 5 horas
                return request.redirect('/shop')
            msg = _("Contraseña incorrecta. Intenta de nuevo.")
        return request.render('web_enhancement.shop_gate', {'msg': msg})
