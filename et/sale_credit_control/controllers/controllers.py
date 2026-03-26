# -*- coding: utf-8 -*-
# from odoo import http


# class NewStock(http.Controller):
#     @http.route('/new_stock/new_stock', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/new_stock/new_stock/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('new_stock.listing', {
#             'root': '/new_stock/new_stock',
#             'objects': http.request.env['new_stock.new_stock'].search([]),
#         })

#     @http.route('/new_stock/new_stock/objects/<model("new_stock.new_stock"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('new_stock.object', {
#             'object': obj
#         })
