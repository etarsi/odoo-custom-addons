# -*- coding: utf-8 -*-
# from odoo import http


# class InternalUse(http.Controller):
#     @http.route('/internal_use/internal_use', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/internal_use/internal_use/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('internal_use.listing', {
#             'root': '/internal_use/internal_use',
#             'objects': http.request.env['internal_use.internal_use'].search([]),
#         })

#     @http.route('/internal_use/internal_use/objects/<model("internal_use.internal_use"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('internal_use.object', {
#             'object': obj
#         })
