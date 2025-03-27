# -*- coding: utf-8 -*-
# from odoo import http


# class AccountEnhancement(http.Controller):
#     @http.route('/account_enhancement/account_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/account_enhancement/account_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('account_enhancement.listing', {
#             'root': '/account_enhancement/account_enhancement',
#             'objects': http.request.env['account_enhancement.account_enhancement'].search([]),
#         })

#     @http.route('/account_enhancement/account_enhancement/objects/<model("account_enhancement.account_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('account_enhancement.object', {
#             'object': obj
#         })
