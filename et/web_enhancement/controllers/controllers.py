# -*- coding: utf-8 -*-
# from odoo import http


# class WebEnhancement(http.Controller):
#     @http.route('/web_enhancement/web_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/web_enhancement/web_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('web_enhancement.listing', {
#             'root': '/web_enhancement/web_enhancement',
#             'objects': http.request.env['web_enhancement.web_enhancement'].search([]),
#         })

#     @http.route('/web_enhancement/web_enhancement/objects/<model("web_enhancement.web_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('web_enhancement.object', {
#             'object': obj
#         })
