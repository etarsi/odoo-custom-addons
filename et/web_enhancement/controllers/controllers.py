from odoo import http
from odoo.http import request
import os
import io
import zipfile

BASE_DIR = '/opt/odoo15/image'

class ProductImageController(http.Controller):

    @http.route('/product/<int:product_id>/images.zip', type='http', auth='public', website=True)
    def download_product_images_zip(self, product_id, **kwargs):
        product = request.env['product.template'].sudo().browse(product_id)
        if not product.exists():
            return request.not_found()

        images = product.gallery_image_ids.filtered(lambda i: i.website_published)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for img in images:
                file_path = os.path.normpath(os.path.join(BASE_DIR, img.relative_path))
                if os.path.isfile(file_path) and file_path.startswith(os.path.abspath(BASE_DIR)):
                    zf.write(file_path, arcname=img.filename)

        headers = [
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', 'attachment; filename="%s_images.zip"' % (product.default_code or product.id)),
        ]
        return request.make_response(buffer.getvalue(), headers=headers)