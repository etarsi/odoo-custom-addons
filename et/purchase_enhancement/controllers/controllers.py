# -*- coding: utf-8 -*-
# from odoo import http


# class PurchaseEnhancement(http.Controller):
#     @http.route('/purchase_enhancement/purchase_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/purchase_enhancement/purchase_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('purchase_enhancement.listing', {
#             'root': '/purchase_enhancement/purchase_enhancement',
#             'objects': http.request.env['purchase_enhancement.purchase_enhancement'].search([]),
#         })

#     @http.route('/purchase_enhancement/purchase_enhancement/objects/<model("purchase_enhancement.purchase_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('purchase_enhancement.object', {
#             'object': obj
#         })
