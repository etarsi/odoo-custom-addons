# -*- coding: utf-8 -*-
# from odoo import http


# class StockEnhancement(http.Controller):
#     @http.route('/stock_enhancement/stock_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stock_enhancement/stock_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('stock_enhancement.listing', {
#             'root': '/stock_enhancement/stock_enhancement',
#             'objects': http.request.env['stock_enhancement.stock_enhancement'].search([]),
#         })

#     @http.route('/stock_enhancement/stock_enhancement/objects/<model("stock_enhancement.stock_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stock_enhancement.object', {
#             'object': obj
#         })
