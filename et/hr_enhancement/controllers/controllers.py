# -*- coding: utf-8 -*-
# from odoo import http


# class HrEnhancement(http.Controller):
#     @http.route('/hr_enhancement/hr_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hr_enhancement/hr_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('hr_enhancement.listing', {
#             'root': '/hr_enhancement/hr_enhancement',
#             'objects': http.request.env['hr_enhancement.hr_enhancement'].search([]),
#         })

#     @http.route('/hr_enhancement/hr_enhancement/objects/<model("hr_enhancement.hr_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hr_enhancement.object', {
#             'object': obj
#         })
