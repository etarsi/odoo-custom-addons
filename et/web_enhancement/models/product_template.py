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

def _leading_code(name):
    """
    Devuelve el primer bloque de código al inicio del nombre.
    Soporta: '52358 - 55781', '52358_...', '52358 – ...', '[52358] ...'
    """
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

    @lru_cache(maxsize=4096)
    def _get_parents_cached(self, service, file_id):
        """Devuelve la lista de padres (IDs) de un file/folder, cacheado."""
        try:
            meta = service.files().get(
                fileId=file_id,
                fields="parents",
                supportsAllDrives=True,
            ).execute()
        except HttpError:
            return []
        return meta.get("parents", []) or []

    def _is_descendant_of(self, service, folder_id, ancestor_id):
        """
        True si folder_id es la misma que ancestor_id o está debajo (en cualquier nivel).
        Recorre padres hacia arriba (My Drive o Shared Drive) usando 'parents'.
        """
        seen = set()
        current = [folder_id]
        while current:
            nxt = []
            for fid in current:
                if fid in seen:
                    continue
                seen.add(fid)
                if fid == ancestor_id:
                    return True
                parents = self._get_parents_cached(service, fid)
                nxt.extend(parents)
            current = nxt
        return False

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

    def _gdrive_list_subfolders(self, service, parent_id):
        """Devuelve subcarpetas directas de parent_id."""
        q = (
            f"'{parent_id}' in parents and trashed=false and "
            "mimeType='application/vnd.google-apps.folder'"
        )
        folders, page_token = [], None
        while True:
            resp = service.files().list(
                q=q,
                fields="nextPageToken, files(id,name,mimeType)",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            folders.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return folders


    def _find_subfolder_for_code(self, service, main_folder_id, code, max_depth=None):
        """
        Busca subcarpetas en TODOS los niveles por debajo de main_folder_id.
        Ej: main/c1/c2/c3/c4...
        """
        code_str = _nfc((code or "").strip())
        if not code_str:
            return None
        code_l = code_str.lower()

        # stack: (folder_id, depth)
        stack = [(main_folder_id, 0)]
        visited = set()
        candidates = []  # [(folder_dict, depth)]

        while stack:
            current_id, depth = stack.pop()
            if current_id in visited:
                continue
            visited.add(current_id)

            if max_depth is not None and depth >= max_depth:
                continue

            subfolders = self._gdrive_list_subfolders(service, current_id)

            for f in subfolders:
                name = _nfc((f.get("name") or "").strip())
                lead = (_leading_code(name) or "").lower()

                # match por código al inicio (52358 - ..., 52358_..., [52358] ...)
                if lead == code_l:
                    candidates.append((f, depth + 1))

                # seguir bajando niveles
                stack.append((f["id"], depth + 1))

        if not candidates:
            return None

        # scoring: nombre exacto > prefijo por código > menor profundidad > nombre más corto
        def score(item):
            f, depth = item
            name = _nfc((f.get("name") or "").strip())
            name_l = name.lower()

            if name_l == code_l:
                rank = 3
            elif (_leading_code(name) or "").lower() == code_l:
                rank = 2
            else:
                rank = 1

            # preferir menos profundidad y nombre más corto
            return (rank, -depth, -len(name))

        best, best_depth = max(candidates, key=score)
        return {
            "id": best["id"],
            "name": best.get("name"),
            "depth": best_depth,
        }

    def _create_product_download_mark(self, description=None):
        self.env['product.download.mark'].create({
            'product_id': self.id,
            'download_mark': True,
            'description': description,
            'date': datetime.now(),
        })

    # --------- Acción: ZIP por default_code ---------
    def action_zip_by_default_code_from_main_folder(self):
        self.ensure_one()
        self = self.sudo()
        service = self._build_gdrive_service()
        attachments = []
        sheet_drive_folder_path = self.env['ir.config_parameter'].get_param('web_enhancement.sheet_drive_folder_path')
        if not sheet_drive_folder_path:
            _logger.info("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
            #crear un registro en el product download mark
            self._create_product_download_mark(description="No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
            raise UserError(_("Se produjo un error al obtener las imagenes, por favor contáctese a soporte."))
        
        def _add_file_to_zip(zipf, file_obj, arc_prefix):
            file_id = file_obj["id"]
            file_name = file_obj.get("name") or file_id
            buf = io.BytesIO()
            req = service.files().get_media(fileId=file_id)
            downloader = MediaIoBaseDownload(buf, req, chunksize=8*1024*1024)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            data = buf.getvalue()
            if not data:
                _logger.warning("Archivo vacío: %s (%s)", file_name, file_id)
                return
            arc = os.path.join(arc_prefix, file_name) if arc_prefix else file_name
            arc = "/".join(arc.split(os.sep))
            zipf.writestr(arc, data)

        def _walk_and_zip(zipf, folder_id, prefix):
            items = self._gdrive_list_folder_items(service, folder_id)
            for it in items:
                it = self._gdrive_resolve_shortcut(service, it) 
                mime = it.get("mimeType")
                name = it.get("name") or it["id"]
                if mime == "application/vnd.google-apps.folder":
                    sub_prefix = f"{prefix}/{name}" if prefix else name
                    # entrada de directorio (opcional)
                    zinfo = zipfile.ZipInfo(f"{sub_prefix}/")
                    zipf.writestr(zinfo, b"")
                    _walk_and_zip(zipf, it["id"], sub_prefix)
                else:
                    if _is_image(it):
                        _add_file_to_zip(zipf, it, prefix)

        for tmpl in self:
            # ---- Determinar carpeta objetivo y nombre raíz del ZIP ----
            if (tmpl.gdrive_folder_id or "").strip():
                # Caso 1: usar la carpeta del producto directamente
                code = tmpl.gdrive_folder_id.strip()
                # Obtener nombre legible de esa carpeta para el prefijo del ZIP
                try:
                    sub = service.files().get(
                        fileId=code, fields="id,name,mimeType", supportsAllDrives=True
                    ).execute()
                except HttpError:
                    sub = None
                #si no encuentra la carpeta, que vuelva a buscar con la carpeta padre
                if not sub:
                    main_id = (sheet_drive_folder_path or "").strip()
                    if not main_id:
                        self._create_product_download_mark(description="No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
                        _logger.info("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
                        raise UserError(_("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive)."))
                    code = (tmpl.default_code or "").strip()
                    if not code:
                        self._create_product_download_mark(description="No está configurado el default_code para el producto '%s'." % tmpl.display_name)
                        _logger.info("No está configurado el default_code para el producto '%s'." % tmpl.display_name)
                        raise UserError(_("No está configurado el default_code para el producto '%s'." % tmpl.display_name))

                    sub = self._find_subfolder_for_code(service, main_id, code)
                    if not sub:
                        self._create_product_download_mark(description="No se encontró subcarpeta para el código '%s' dentro de la carpeta principal." % code)
                        _logger.info("No se encontró subcarpeta para el código '%s' dentro de la carpeta principal." % code)
                        raise UserError(_("No se encontró subcarpeta para el código '%s' dentro de la carpeta principal." % code))
                    target_folder_id = sub["id"]
                    root_prefix = (sub.get("name") or code).strip().replace("/", "_")
                else:
                    target_folder_id = sub["id"]
                    root_prefix = (sub.get("name") or tmpl.default_code or f"product_{tmpl.id}").strip().replace("/", "_")
            else:
                # Caso 2: usar carpeta principal global y buscar subcarpeta por default_code
                main_id = (sheet_drive_folder_path or "").strip()
                if not main_id:
                    self._create_product_download_mark(description="No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
                    _logger.info("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
                    raise UserError(_("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive)."))
                code = (tmpl.default_code or "").strip()
                if not code:
                    self._create_product_download_mark(description="No está configurado el default_code para el producto '%s'." % tmpl.display_name)
                    _logger.info("No está configurado el default_code para el producto '%s'." % tmpl.display_name)
                    raise UserError(_("No está configurado el default_code para el producto '%s'." % tmpl.display_name))

                sub = self._find_subfolder_for_code(service, main_id, code)
                if not sub:
                    self._create_product_download_mark(description="No se encontró subcarpeta para el código '%s' dentro de la carpeta principal." % code)
                    _logger.info("No se encontró subcarpeta para el código '%s' dentro de la carpeta principal." % code)
                    raise UserError(_("No se encontró subcarpeta para el código '%s' dentro de la carpeta principal." % code))
                target_folder_id = sub["id"]
                root_prefix = (sub.get("name") or code).strip().replace("/", "_")   
            # Armar ZIP SOLO de esa subcarpeta
            mem = io.BytesIO()
            with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_STORED) as zipf:
                _walk_and_zip(zipf, target_folder_id, root_prefix)
            mem.seek(0)
            data_b64 = base64.b64encode(mem.getvalue()).decode()
            zip_name = f"{(tmpl.name or code).strip().replace('/', '_')}_imagenes.zip"

            attach = self.env["ir.attachment"].sudo().create({
                "name": zip_name,
                "datas": data_b64,
                "res_model": tmpl._name,
                "res_id": tmpl.id,
                "mimetype": "application/zip",
                "public": True,
            })
            #generar token si no tiene
            if not attach.access_token:
                attach._generate_access_token()
            attachments.append(attach.id)
            _logger.info("ZIP creado para '%s' (subcarpeta '%s') -> attachment id %s",
                         tmpl.display_name, sub.get("name"), attach.id)
            #guardar el id en el campo del producto
            tmpl.write({'gdrive_folder_id': target_folder_id})
        # Si es un solo producto, devuelvo descarga directa
        if len(self) == 1 and attachments:
            att = self.env["ir.attachment"].browse(attachments[-1])
            if not att.access_token:
                att._generate_access_token()
            url = f"/web/content/{att.id}?download=true"
            return {
                "type": "ir.actions.act_url",
                "url": url,
                "target": "self",
            }


    def update_image_product_web(self):
        for template in self:
            # Actualizar imagenes del producto desde el drive si tiene carpeta asignada y tambien en la tabla product.image
            if template.gdrive_folder_id:
                template._update_image_from_gdrive()
                
    def _update_image_from_gdrive(self):
        self.ensure_one()
        self = self.sudo()
        service = self._build_gdrive_service()
        folder_id = self.gdrive_folder_id.strip()
        if not folder_id:
            return
        items = self._gdrive_list_folder_items(service, folder_id)
        image_files = []
        for it in items:
            it = self._gdrive_resolve_shortcut(service, it)
            if _is_image(it):
                image_files.append(it)
        if not image_files:
            return
        # Borrar imágenes actuales
        if self.product_template_image_ids:
            self.product_template_image_ids.unlink()
        self._actualizar_foto_principal_desde_gdrive(image_files, service)
        # Descargar e insertar nuevas imágenes
        for file_obj in image_files:
            file_id = file_obj["id"]
            file_name = file_obj.get("name") or file_id
            buf = io.BytesIO()
            req = service.files().get_media(fileId=file_id)
            downloader = MediaIoBaseDownload(buf, req, chunksize=8*1024*1024)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            data = buf.getvalue()
            if not data:
                _logger.warning("Archivo vacío al actualizar imagen: %s (%s)", file_name, file_id)
                continue
            data_b64 = base64.b64encode(data)
            image_extra = data_b64.decode('ascii')
            self.env['product.image'].create({
                'product_tmpl_id': self.id,
                'image_1920': image_extra,
                'name': self.id,
            })

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
        
    def _actualizar_gdrive_folder_id_desde_default_code(self):
        for record in self:
            service = record._build_gdrive_service()
            sheet_drive_folder_path = record.env['ir.config_parameter'].get_param('web_enhancement.sheet_drive_folder_path')
            if not sheet_drive_folder_path:
                _logger.info("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
                return
            main_id = (sheet_drive_folder_path or "").strip()
            if not main_id:
                _logger.info("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
                return
            code = (record.default_code or "").strip()
            if not code:
                _logger.info("No está configurado el default_code para el producto '%s'." % record.display_name)
                return
            sub = record._find_subfolder_for_code(service, main_id, code)
            if not sub:
                _logger.info("No se encontró subcarpeta para el código '%s' dentro de la carpeta principal." % code)
                return
            target_folder_id = sub["id"]
            record.write({'gdrive_folder_id': target_folder_id})