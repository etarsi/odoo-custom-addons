# -*- coding: utf-8 -*-
# from odoo import http


# class SaleEnhancement(http.Controller):
#     @http.route('/sale_enhancement/sale_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sale_enhancement/sale_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sale_enhancement.listing', {
#             'root': '/sale_enhancement/sale_enhancement',
#             'objects': http.request.env['sale_enhancement.sale_enhancement'].search([]),
#         })

#     @http.route('/sale_enhancement/sale_enhancement/objects/<model("sale_enhancement.sale_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sale_enhancement.object', {
#             'object': obj
#         })
