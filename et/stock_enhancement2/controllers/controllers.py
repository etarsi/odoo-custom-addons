# -*- coding: utf-8 -*-
# from odoo import http


# class StockEnhancement2(http.Controller):
#     @http.route('/stock_enhancement2/stock_enhancement2', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stock_enhancement2/stock_enhancement2/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('stock_enhancement2.listing', {
#             'root': '/stock_enhancement2/stock_enhancement2',
#             'objects': http.request.env['stock_enhancement2.stock_enhancement2'].search([]),
#         })

#     @http.route('/stock_enhancement2/stock_enhancement2/objects/<model("stock_enhancement2.stock_enhancement2"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stock_enhancement2.object', {
#             'object': obj
#         })
