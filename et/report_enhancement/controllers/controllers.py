# -*- coding: utf-8 -*-
# from odoo import http


# class .\odoo-custom-addons\et\report-enhancement(http.Controller):
#     @http.route('/.\odoo-custom-addons\et\report-enhancement/.\odoo-custom-addons\et\report-enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/.\odoo-custom-addons\et\report-enhancement/.\odoo-custom-addons\et\report-enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('.\odoo-custom-addons\et\report-enhancement.listing', {
#             'root': '/.\odoo-custom-addons\et\report-enhancement/.\odoo-custom-addons\et\report-enhancement',
#             'objects': http.request.env['.\odoo-custom-addons\et\report-enhancement..\odoo-custom-addons\et\report-enhancement'].search([]),
#         })

#     @http.route('/.\odoo-custom-addons\et\report-enhancement/.\odoo-custom-addons\et\report-enhancement/objects/<model(".\odoo-custom-addons\et\report-enhancement..\odoo-custom-addons\et\report-enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('.\odoo-custom-addons\et\report-enhancement.object', {
#             'object': obj
#         })
