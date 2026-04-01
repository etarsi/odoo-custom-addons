
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
        
        
    # --------- Acción: ZIP por default_code ---------
    def _get_local_image_base_dir(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'web_enhancement.local_image_base_path'
        )
        return (param or '/opt/odoo15/image').strip()

    def action_zip_images_from_local_folder(self):
        self.ensure_one()
        self = self.sudo()

        base_dir = self._get_local_image_base_dir()
        if not os.path.isdir(base_dir):
            _logger.info("La carpeta base de imágenes no existe: %s", base_dir)
            if hasattr(self, '_create_product_download_mark'):
                self._create_product_download_mark(
                    description="La carpeta base de imágenes no existe: %s" % base_dir
                )
            raise UserError(_("Se produjo un error al obtener las imágenes, por favor contáctese a soporte."))

        attachments = []

        for tmpl in self:
            images = tmpl.gallery_image_ids.sorted(
                key=lambda r: ((0 if r.is_main else 1), r.sequence, r.id)
            )

            if not images:
                _logger.info("El producto '%s' no tiene imágenes en la galería.", tmpl.display_name)
                if hasattr(self, '_create_product_download_mark'):
                    tmpl._create_product_download_mark(
                        description="El producto '%s' no tiene imágenes en la galería." % tmpl.display_name
                    )
                raise UserError(_("El producto '%s' no tiene imágenes para descargar.") % tmpl.display_name)

            root_prefix = (
                (tmpl.default_code or tmpl.name or ("product_%s" % tmpl.id))
                .strip()
                .replace("/", "_")
            )

            mem = io.BytesIO()
            added = 0
            used_names = set()

            with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
                for img in images:
                    rel_path = (img.relative_path or '').strip().replace('\\', '/')
                    if not rel_path:
                        _logger.warning("Imagen sin relative_path. ID galería: %s", img.id)
                        continue

                    abs_path = os.path.normpath(os.path.join(base_dir, rel_path))
                    base_abs = os.path.abspath(base_dir)

                    # seguridad: evitar salir de la carpeta base
                    if not abs_path.startswith(base_abs):
                        _logger.warning(
                            "Ruta inválida fuera de base_dir. Producto: %s | rel_path: %s | abs_path: %s",
                            tmpl.display_name, rel_path, abs_path
                        )
                        continue

                    if not os.path.isfile(abs_path):
                        _logger.warning(
                            "Archivo no encontrado. Producto: %s | rel_path: %s | abs_path: %s",
                            tmpl.display_name, rel_path, abs_path
                        )
                        continue

                    filename = (img.filename or os.path.basename(abs_path) or ('image_%s' % img.id)).strip()
                    if not filename:
                        filename = 'image_%s' % img.id

                    # evitar nombres repetidos dentro del zip
                    zip_filename = filename
                    if zip_filename in used_names:
                        name, ext = os.path.splitext(filename)
                        i = 1
                        while True:
                            candidate = "%s_%s%s" % (name, i, ext)
                            if candidate not in used_names:
                                zip_filename = candidate
                                break
                            i += 1
                    used_names.add(zip_filename)

                    arcname = "%s/%s" % (root_prefix, zip_filename)

                    with open(abs_path, 'rb') as f:
                        zipf.writestr(arcname, f.read())

                    added += 1

            if not added:
                _logger.info("No se encontraron imágenes válidas para '%s'.", tmpl.display_name)
                if hasattr(self, '_create_product_download_mark'):
                    tmpl._create_product_download_mark(
                        description="No se encontraron imágenes válidas para '%s'." % tmpl.display_name
                    )
                raise UserError(_("No se encontraron imágenes válidas para '%s'.") % tmpl.display_name)

            mem.seek(0)
            data_b64 = base64.b64encode(mem.getvalue()).decode()

            zip_name = "%s_imagenes.zip" % (
                (tmpl.name or tmpl.default_code or ('product_%s' % tmpl.id))
                .strip()
                .replace('/', '_')
            )

            # opcional: borrar zips viejos del mismo producto
            old_attachments = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', tmpl._name),
                ('res_id', '=', tmpl.id),
                ('name', '=', zip_name),
                ('mimetype', '=', 'application/zip'),
            ])
            if old_attachments:
                old_attachments.unlink()

            attach = self.env['ir.attachment'].sudo().create({
                'name': zip_name,
                'datas': data_b64,
                'res_model': tmpl._name,
                'res_id': tmpl.id,
                'mimetype': 'application/zip',
                'public': True,
            })

            if not attach.access_token:
                attach._generate_access_token()

            attachments.append(attach.id)

            _logger.info(
                "ZIP local creado para '%s' con %s imágenes -> attachment id %s",
                tmpl.display_name, added, attach.id
            )

        if len(self) == 1 and attachments:
            att = self.env['ir.attachment'].sudo().browse(attachments[-1])
            if not att.access_token:
                att._generate_access_token()

            url = "/web/content/%s?download=true" % att.id
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'self',
            }

        return True