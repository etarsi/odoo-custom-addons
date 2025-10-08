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
            url="/listado_productos",
            total=total,
            page=page,
            step=page_size,
            scope=5,
            url_args={'search': search} if search else None,
        )

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
        
        def to_int_page(x, default=1):
            if isinstance(x, dict):
                x = x.get('page', default)
            try:
                return int(x)
            except Exception:
                return default

        page_cur = to_int_page(pager.get('page'), 1)
        page_count = to_int_page(pager.get('page_count'), page_cur)

        norm_pages = []
        for it in pager.get('pages', []):
            norm_pages.append({
                'page': to_int_page(it.get('page'), 1),
                'title': it.get('title'),
            })
        pager['pages'] = norm_pages

        values.update({
            'pager': pager,
            'page_cur': page_cur,
            'is_first_page': page_cur <= 1,
            'is_last_page': page_cur >= page_count,
        })
        _logger.info("PAGER PAGE = %r", pager.get('page'))
        # Render por t-name (QWeb puro)
        return request.render('web_enhancement.product_list_qweb', values)
