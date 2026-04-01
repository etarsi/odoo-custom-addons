# models/product_image_gallery.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import os

class ProductImageGallery(models.Model):
    _name = 'product.image.gallery'
    _description = 'Galería de imágenes de producto'
    _order = 'sequence, id'

    product_tmpl_id = fields.Many2one(
        'product.template',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char('Nombre')
    sequence = fields.Integer(default=10)
    is_main = fields.Boolean('Principal')
    website_published = fields.Boolean(default=True)

    filename = fields.Char('Archivo', required=True)
    relative_path = fields.Char('Ruta relativa', required=True)
    image_url = fields.Char(
        'URL',
        compute='_compute_image_url',
        store=False
    )

    @api.depends('relative_path')
    def _compute_image_url(self):
        for rec in self:
            rec.image_url = '/product-images/%s' % rec.relative_path if rec.relative_path else False