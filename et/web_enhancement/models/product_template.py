
import zipfile, mimetypes, logging, base64, io, os, zipfile
from datetime import datetime
import unicodedata, re, os
from functools import lru_cache
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.mimetypes import guess_mimetype

_logger = logging.getLogger(__name__)

ALLOWED_IMAGE_MIMES = ("image/jpeg", "image/png")
ALLOWED_IMAGE_EXTS = (".jpg", ".jpeg", ".png")

class ProductTemplate(models.Model):
    _inherit = "product.template"

    gdrive_folder_id = fields.Char('Google Drive Folder ID')
    gallery_image_ids = fields.One2many('product.image.gallery', 'product_tmpl_id', string='Galería')
    website_main_image_url = fields.Char(string='Imagen principal website', compute='_compute_website_main_image_url')

    @api.depends('gallery_image_ids.is_main', 'gallery_image_ids.relative_path', 'gallery_image_ids.sequence')
    def _compute_website_main_image_url(self):
        for product in self:
            product_sudo = product.sudo()

            main_img = product_sudo.gallery_image_ids.filtered(lambda x: x.is_main)[:1]
            if not main_img:
                main_img = product_sudo.gallery_image_ids.sorted(
                    key=lambda x: (x.sequence, x.id)
                )[:1]
            product.website_main_image_url = main_img.image_url if main_img else False    

    def _extract_default_code_from_name(self, name):
        """
        Ejemplos:
        66779_112 -> 66779
        66779 foto -> 66779
        66779 -> 66779
        """
        if not name:
            return False

        name = os.path.splitext(name)[0].strip()
        if not name:
            return False

        parts = re.split(r'[_\s]+', name, maxsplit=1)
        code = (parts[0] or '').strip()
        return code or False

    def _find_default_code_in_path(self, current_root, base_dir, product_by_code):
        """
        Busca un código válido en la ruta de carpetas, desde la más interna
        hacia arriba.

        Ejemplo:
        /opt/odoo15/image/MUÑECAS/66779_112/FOTOS
        prueba:
        FOTOS -> no
        66779_112 -> 66779 -> sí
        MUÑECAS -> no
        """
        rel_root = os.path.relpath(current_root, base_dir).replace('\\', '/')
        if rel_root in ('.', '', '/'):
            return False

        parts = [p for p in rel_root.split('/') if p]

        for part in reversed(parts):
            code = self._extract_default_code_from_name(part)
            if code and code in product_by_code:
                return code

        return False

    def action_sync_all_images_from_disk(self):
        base_dir = '/opt/odoo15/image'
        allowed_ext = ('.jpg', '.jpeg', '.png', '.webp')
        ignored_folders = {'web', 'thumb', 'original'}

        if not os.path.isdir(base_dir):
            raise UserError(_('La carpeta %s no existe.') % base_dir)

        products = self.env['product.template'].search([('default_code', '!=', False)])
        product_by_code = {
            (p.default_code or '').strip(): p
            for p in products
        }

        Gallery = self.env['product.image.gallery']

        created = 0
        updated = 0
        ignored = 0

        # Evita duplicados por ruta
        existing = {
            g.relative_path: g
            for g in Gallery.search([])
        }

        # Secuencia por producto
        seq_by_product = {}

        for root, dirs, files in os.walk(base_dir):
            # Ignorar carpetas no deseadas
            dirs[:] = [d for d in dirs if d.lower() not in ignored_folders]

            # 1) Buscar código en cualquier carpeta de la ruta
            folder_code = self._find_default_code_in_path(root, base_dir, product_by_code)

            for fname in files:
                if not fname.lower().endswith(allowed_ext):
                    continue

                # 2) Si no encontró en carpeta, intentar por archivo
                file_code = self._extract_default_code_from_name(fname)

                code = folder_code or file_code
                if not code:
                    ignored += 1
                    continue

                product = product_by_code.get(code)
                if not product:
                    ignored += 1
                    continue

                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, base_dir).replace('\\', '/')

                seq = seq_by_product.get(product.id, 10)

                vals = {
                    'product_tmpl_id': product.id,
                    'name': fname,
                    'filename': fname,
                    'relative_path': rel_path,
                    'sequence': seq,
                }

                if rel_path in existing:
                    existing[rel_path].write(vals)
                    updated += 1
                else:
                    rec = Gallery.create(vals)
                    existing[rel_path] = rec
                    created += 1

                seq_by_product[product.id] = seq + 10

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización finalizada'),
                'message': _('Creadas: %s | Actualizadas: %s | Ignoradas: %s') % (
                    created, updated, ignored
                ),
                'type': 'success',
                'sticky': False,
            }
        }