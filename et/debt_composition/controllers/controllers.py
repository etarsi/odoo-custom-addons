# -*- coding: utf-8 -*-
# from odoo import http


# class DebtComposition(http.Controller):
#     @http.route('/debt_composition/debt_composition', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/debt_composition/debt_composition/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('debt_composition.listing', {
#             'root': '/debt_composition/debt_composition',
#             'objects': http.request.env['debt_composition.debt_composition'].search([]),
#         })

#     @http.route('/debt_composition/debt_composition/objects/<model("debt_composition.debt_composition"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('debt_composition.object', {
#             'object': obj
#         })
