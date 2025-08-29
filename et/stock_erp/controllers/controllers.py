# -*- coding: utf-8 -*-
# from odoo import http


# class StockErp(http.Controller):
#     @http.route('/stock_erp/stock_erp', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stock_erp/stock_erp/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('stock_erp.listing', {
#             'root': '/stock_erp/stock_erp',
#             'objects': http.request.env['stock_erp.stock_erp'].search([]),
#         })

#     @http.route('/stock_erp/stock_erp/objects/<model("stock_erp.stock_erp"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stock_erp.object', {
#             'object': obj
#         })
