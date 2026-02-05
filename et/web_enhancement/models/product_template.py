# -*- coding: utf-8 -*-
import io
import os
import base64
import logging
import zipfile
from datetime import datetime
from googleapiclient.errors import HttpError
import unicodedata, re
from functools import lru_cache
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ALLOWED_IMAGE_MIMES = ("image/jpeg", "image/png")
ALLOWED_IMAGE_EXTS = (".jpg", ".jpeg", ".png")

def _is_image(file_obj):
    mime = (file_obj.get("mimeType") or "").lower()
    name = (file_obj.get("name") or "").lower()
    return (mime in ALLOWED_IMAGE_MIMES) or name.endswith(ALLOWED_IMAGE_EXTS)

def _nfc(s):
    return unicodedata.normalize("NFC", s or "")

def _escape_q(s):
    # escape simple para query de Drive
    return (s or "").replace("\\", "\\\\").replace("'", "\\'")

def _leading_code(name):
    s = (name or "")
    m = re.match(r'^\s*[\[\(\{]*\s*([0-9A-Za-z]+)', s)
    return m.group(1) if m else None

class ProductTemplate(models.Model):
    _inherit = "product.template"

    gdrive_folder_id = fields.Char(
        string="Google Drive Folder ID",
        help="ID de la carpeta PRINCIPAL en Drive. Dentro habrá subcarpetas por default_code.",
    )

    # --------- Google Drive helpers ---------
    def _build_gdrive_service(self):
        sa_path = "/opt/odoo15/drive-api/service_account.json"
        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def _gdrive_list_folder_items(self, service, folder_id):
        items = []
        q = f"'{folder_id}' in parents and trashed=false"
        page_token = None
        while True:
            resp = service.files().list(
                q=q,
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            items.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return items

    def _gdrive_resolve_shortcut(self, service, file_obj):
        if file_obj.get("mimeType") == "application/vnd.google-apps.shortcut":
            real = service.files().get(
                fileId=file_obj["id"],
                fields="id,name,mimeType,shortcutDetails(targetId,targetMimeType)",
                supportsAllDrives=True,
            ).execute()
            target_id = real.get("shortcutDetails", {}).get("targetId")
            if target_id:
                return service.files().get(
                    fileId=target_id,
                    fields="id,name,mimeType,shortcutDetails(targetId,targetMimeType)",
                    supportsAllDrives=True,
                ).execute()
        return file_obj

    def _create_product_download_mark(self, description=None):
        self.env['product.download.mark'].create({
            'product_id': self.id,
            'download_mark': True,
            'description': description,
            'date': datetime.now(),
        })

    # --------- Acción: ZIP por default_code ---------
    def _actualizar_foto_principal_desde_gdrive(self, image_files, service):
        # Actualiza la foto principal (image_1920) del producto con la primera imagen encontrada en Drive
        if not image_files:
            return
        first_image = image_files[0]
        file_id = first_image["id"]
        file_name = first_image.get("name") or file_id
        buf = io.BytesIO()
        req = service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(buf, req, chunksize=8*1024*1024)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        data = buf.getvalue()
        if not data:
            _logger.warning("Archivo vacío al actualizar foto principal: %s (%s)", file_name, file_id)
            return
        data_b64 = base64.b64encode(data)
        image_1920 = data_b64.decode('ascii')
        self.write({'image_1920': image_1920})
                
    @lru_cache(maxsize=50000)
    def _get_parents_cached(self, service, file_id):
        try:
            meta = service.files().get(
                fileId=file_id,
                fields="parents",
                supportsAllDrives=True,
            ).execute()
            return tuple(meta.get("parents", []) or [])
        except Exception:
            return tuple()

    def _is_descendant_with_seed_parents(self, service, seed_parents, ancestor_id):
        """Sube por parents hasta encontrar ancestor_id."""
        seen = set()
        stack = list(seed_parents or [])
        while stack:
            pid = stack.pop()
            if pid in seen:
                continue
            seen.add(pid)
            if pid == ancestor_id:
                return True
            stack.extend(self._get_parents_cached(service, pid))
        return False

    def _find_subfolder_for_code(self, service, main_folder_id, code):
        """
        Búsqueda rápida:
        - Drive indexa por nombre (name contains)
        - luego filtramos por leading code y pertenencia al árbol main_folder_id
        """
        code_str = _nfc((code or "").strip())
        if not code_str:
            return None
        code_l = code_str.lower()
        esc = _escape_q(code_str)

        # 1) query global por nombre (rápido)
        q = (
            "mimeType='application/vnd.google-apps.folder' and trashed=false and "
            f"(name = '{esc}' or name contains '{esc}')"
        )

        candidates = []
        page_token = None
        while True:
            resp = service.files().list(
                q=q,
                fields="nextPageToken, files(id,name,parents)",
                pageSize=1000,
                pageToken=page_token,
                corpora="allDrives",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            ).execute()

            for f in resp.get("files", []):
                name = _nfc((f.get("name") or "").strip())
                lead = (_leading_code(name) or "").lower()

                # 2) filtro por código al inicio
                if lead != code_l:
                    continue

                # 3) asegurar que está bajo tu carpeta principal
                if self._is_descendant_with_seed_parents(
                    service, f.get("parents", []), main_folder_id
                ):
                    candidates.append(f)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        if not candidates:
            return None

        # scoring: exacto > prefijo, y nombre más corto
        def score(f):
            name = _nfc((f.get("name") or "").strip())
            if name.lower() == code_l:
                return (3, -len(name))
            return (2, -len(name))

        best = max(candidates, key=score)
        return {"id": best["id"], "name": best.get("name")}
    
    def action_sync_gdrive_link_and_images(self):
        """
        1) Si falta gdrive_folder_id -> lo busca por default_code
        2) Con gdrive_folder_id -> actualiza foto principal + galería (product.image)
        Todo en una sola acción masiva.
        """
        if not self:
            raise UserError(_("No hay productos seleccionados."))

        service = self._build_gdrive_service()
        main_id = (self.env["ir.config_parameter"].get_param("web_enhancement.sheet_drive_folder_path") or "").strip()

        updated_link = 0
        updated_images = 0
        no_code = 0
        not_found = 0
        errors = 0

        for record in self:
            try:
                # A) Resolver carpeta Drive si falta link
                if not record.gdrive_folder_id:
                    code = (record.default_code or "").strip()
                    if not code:
                        no_code += 1
                        continue

                    sub = record._find_subfolder_for_code(service, main_id, code) if main_id else None
                    if not sub:
                        not_found += 1
                        continue

                    record.write({"gdrive_folder_id": sub["id"]})
                    updated_link += 1

                # B) Actualizar imágenes si ya tiene carpeta
                if record.gdrive_folder_id:
                    ok = record._update_image_from_gdrive(service=service)
                    if ok:
                        updated_images += 1

            except Exception:
                errors += 1
                _logger.exception("Error sincronizando producto %s (%s)", record.display_name, record.id)
                continue

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sincronización Google Drive"),
                "message": _(
                    "Links actualizados: %(l)s | Productos con imágenes actualizadas: %(i)s | "
                    "Sin código: %(c)s | Carpeta no encontrada: %(n)s | Errores: %(e)s"
                ) % {
                    "l": updated_link,
                    "i": updated_images,
                    "c": no_code,
                    "n": not_found,
                    "e": errors,
                },
                "type": "success",
                "sticky": False,
            },
        }

    def _update_image_from_gdrive(self, service=None):
        """Devuelve True si actualizó imágenes, False si no había imágenes/carpeta."""
        self.ensure_one()
        self = self.sudo()
        service = service or self._build_gdrive_service()

        folder_id = (self.gdrive_folder_id or "").strip()
        if not folder_id:
            return False

        items = self._gdrive_list_folder_items(service, folder_id)
        image_files = []
        for it in items:
            it = self._gdrive_resolve_shortcut(service, it)
            if _is_image(it):
                image_files.append(it)

        if not image_files:
            return False

        # Orden estable para que la foto principal sea consistente
        image_files.sort(key=lambda x: (x.get("name") or "").lower())

        # Borrar galería actual
        if self.product_template_image_ids:
            self.product_template_image_ids.unlink()

        # Foto principal
        self._actualizar_foto_principal_desde_gdrive(image_files, service)

        # Galería
        for file_obj in image_files:
            file_id = file_obj["id"]
            file_name = file_obj.get("name") or file_id
            buf = io.BytesIO()
            req = service.files().get_media(fileId=file_id)
            downloader = MediaIoBaseDownload(buf, req, chunksize=8 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            data = buf.getvalue()
            if not data:
                continue

            self.env["product.image"].create({
                "product_tmpl_id": self.id,
                "image_1920": base64.b64encode(data).decode("ascii"),
                "name": file_name,
            })

        return True