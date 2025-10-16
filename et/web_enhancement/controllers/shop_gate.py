# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request

class ShopGate(http.Controller):

    @http.route('/shop/gate', type='http', auth='public', website=True, methods=['GET','POST'])
    def shop_gate(self, **post):
        msg = None
        if request.httprequest.method == 'POST':
            pwd_cfg = '123456' #request.env['ir.config_parameter'].sudo().get_param('website.shop_gate_password') or ''
            if (post.get('password') or '') == pwd_cfg:
                request.session['shop_gate_ok'] = True
                return request.redirect('/shop')   # ahora pasa
            msg = _("Contraseña incorrecta. Intenta de nuevo.")

        # Render muy simple; podés hacer un QWeb propio si querés
        return request.render('website.layout', {
            'main_object': None,
            'body_class': 'o_shop_gate',
            'content': f"""
<div class="container my-5" style="max-width:480px">
  <div class="card shadow-sm">
    <div class="card-body">
      <h3 class="mb-3">Acceso a la tienda</h3>
      {'<div class="alert alert-danger">'+msg+'</div>' if msg else ''}
      <form method="post">
        <div class="mb-3">
          <label class="form-label">Contraseña</label>
          <input class="form-control" name="password" type="password" required autofocus />
        </div>
        <button class="btn btn-primary w-100" type="submit">Entrar</button>
      </form>
    </div>
  </div>
</div>
""",
        })
