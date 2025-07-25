# -*- coding: utf-8 -*-
# from odoo import http


# class WmsEnhancement(http.Controller):
#     @http.route('/wms_enhancement/wms_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/wms_enhancement/wms_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('wms_enhancement.listing', {
#             'root': '/wms_enhancement/wms_enhancement',
#             'objects': http.request.env['wms_enhancement.wms_enhancement'].search([]),
#         })

#     @http.route('/wms_enhancement/wms_enhancement/objects/<model("wms_enhancement.wms_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('wms_enhancement.object', {
#             'object': obj
#         })
