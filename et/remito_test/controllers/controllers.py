# -*- coding: utf-8 -*-
# from odoo import http


# class RemitoTest(http.Controller):
#     @http.route('/remito_test/remito_test', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/remito_test/remito_test/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('remito_test.listing', {
#             'root': '/remito_test/remito_test',
#             'objects': http.request.env['remito_test.remito_test'].search([]),
#         })

#     @http.route('/remito_test/remito_test/objects/<model("remito_test.remito_test"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('remito_test.object', {
#             'object': obj
#         })
