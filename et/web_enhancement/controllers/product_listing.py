# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL
import logging
_logger = logging.getLogger(__name__)

class ProductWebsiteController(http.Controller):

    @http.route(['/listado_productos'], auth='public', website=True)
    def productos(self, page=1, search='', **kw):
        Product = request.env['product.template'].sudo()

        domain = []
        # Si querés mostrar solo productos publicados en website, descomenta:
        # domain.append(('website_published', '=', True))

        if search:
            domain += ['|', ('name', 'ilike', search), ('default_code', 'ilike', search)]

        # paginación
        page = int(page) if str(page).isdigit() else 1
        page_size = 12

        total = Product.search_count(domain)
        pager = request.website.pager(
            url="/productos",
            total=total,
            page=page,
            step=page_size,
            scope=5,
            url_args={'search': search} if search else None,
        )

        page_val = pager.get('page', 1)
        if isinstance(page_val, dict):
            page_cur = page_val.get('page', 1)
        else:
            page_cur = int(page_val or 1)

        values.update({
            'pager': pager,
            'page_cur': page_cur,
            'is_first_page': page_cur <= 1,
            'is_last_page': page_cur >= pager.get('page_count', page_cur),
        })

        products = Product.search(domain, limit=page_size, offset=pager['offset'], order="name asc")

        # prefetch de galería para evitar N+1
        products.mapped('product_template_image_ids').ids

        values = {
            'products': products,
            'search': search,
            'pager': pager,
            'total': total,
            'keep': QueryURL('/listado_productos', search=search),
        }
        _logger.info("PAGER PAGE = %r", pager.get('page'))
        # Render por t-name (QWeb puro)
        return request.render('web_enhancement.product_list_qweb', values)
