# -*- coding: utf-8 -*-
import odoo.http as http
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL

class ProductWebsiteController(http.Controller):

    @http.route(['/productos'], type='http', auth='public', website=True, sitemap=True)
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

        products = Product.search(domain, limit=page_size, offset=pager['offset'], order="name asc")

        # prefetch de galería para evitar N+1
        products.mapped('product_template_image_ids').ids

        values = {
            'products': products,
            'search': search,
            'pager': pager,
            'total': total,
            'keep': QueryURL('/productos', search=search),
        }

        # Render por t-name (QWeb puro)
        return http.request.render('web_enhancement.product_list_page', values)
