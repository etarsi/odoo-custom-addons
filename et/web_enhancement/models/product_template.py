# -*- coding: utf-8 -*-
import io
import os
import base64
import logging
import zipfile
from datetime import datetime

from googleapiclient.errors import HttpError
import unicodedata
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
    """Normaliza Unicode (acentos/ñ) para comparaciones en Python."""
    return unicodedata.normalize("NFC", s or "")

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
                fields="shortcutDetails,targetId",
                supportsAllDrives=True,
            ).execute()
            target_id = real.get("shortcutDetails", {}).get("targetId")
            if target_id:
                return service.files().get(
                    fileId=target_id,
                    fields="id,name,mimeType",
                    supportsAllDrives=True,
                ).execute()
        return file_obj

    def _find_subfolder_for_code(self, service, main_folder_id, code):
        """
        Busca carpetas por nombre en TODO el Drive (incluye Shared Drives y shortcuts),
        y filtra solo las que sean descendientes de main_folder_id.
        Devuelve el mejor match usando un scoring similar al tuyo.
        """
        code_str = _nfc((code or "").strip())
        if not code_str:
            return None

        def _search_folders(name, exact):
            # Incluimos shortcuts y luego resolvemos si apuntan a carpeta
            op = "=" if exact else "contains"
            name_q = name.replace("'", r"\'")
            q = (
                "trashed=false and ("
                f"(mimeType='application/vnd.google-apps.folder' and name {op} '{name_q}') "
                "or "
                f"(mimeType='application/vnd.google-apps.shortcut' and name {op} '{name_q}')"
                ")"
            )
            results = []
            page_token = None
            while True:
                resp = service.files().list(
                    q=q,
                    fields=("nextPageToken, files("
                            "id,name,mimeType,parents,"
                            "shortcutDetails(targetId,targetMimeType))"),
                    pageSize=200,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                ).execute()
                results.extend(resp.get("files", []))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            return results

        def _candidate_real_folder_id(file_obj):
            mt = file_obj.get("mimeType")
            if mt == "application/vnd.google-apps.folder":
                return file_obj["id"]
            if mt == "application/vnd.google-apps.shortcut":
                sd = (file_obj.get("shortcutDetails") or {})
                if sd.get("targetMimeType") == "application/vnd.google-apps.folder":
                    return sd.get("targetId")  # puede ser None si faltan permisos
            return None

        candidates = []
        # 1) Primero exactos, luego contains
        for exact in (True, False):
            found = _search_folders(code_str, exact)
            for f in found:
                real_id = _candidate_real_folder_id(f)
                if not real_id:
                    continue
                # Filtrar para quedarnos solo con las que estén debajo de main_folder_id
                if self._is_descendant_of(service, real_id, main_folder_id):
                    # Para el scoring usamos el 'name' visible del file (shortcut o folder)
                    candidates.append({
                        "id": real_id,
                        "name": f.get("name"),
                    })
            if candidates:
                break

        if not candidates:
            return None

        # Scoring: exact == 3, empieza con "<code> " o "<code>-" o "<code>_" == 2, contains == 1
        def score(f):
            name = _nfc(f.get("name") or "")
            if name == code_str:
                return (3, -len(name))
            if name.lower().startswith((code_str + " ").lower()) \
            or name.lower().startswith((code_str + "-").lower()) \
            or name.lower().startswith((code_str + "_").lower()):
                return (2, -len(name))
            return (1, -len(name))

        candidates.sort(key=score, reverse=True)
        # Devolvemos con el formato que espera tu código (dict con id y name)
        return {"id": candidates[0]["id"], "name": candidates[0]["name"]}

    # --------- Acción: ZIP por default_code ---------
    def action_zip_by_default_code_from_main_folder(self):
        self.ensure_one()
        self = self.sudo()
        service = self._build_gdrive_service()
        attachments = []
        sheet_drive_folder_path = self.env['ir.config_parameter'].get_param('web_enhancement.sheet_drive_folder_path')
        if not sheet_drive_folder_path:
            _logger.info("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
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
                sub = service.files().get(
                    fileId=code,
                    fields="id,name",
                    supportsAllDrives=True
                ).execute()
                #si no encuentra la carpeta, que vuelva a buscar con la carpeta padre
                if not sub:
                    main_id = (sheet_drive_folder_path or "").strip()
                    if not main_id:
                        _logger.info("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
                        raise UserError(_("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive)."))
                    code = (tmpl.default_code or "").strip()
                    if not code:
                        _logger.info("No está configurado el default_code para el producto '%s'." % tmpl.display_name)
                        raise UserError(_("No está configurado el default_code para el producto '%s'." % tmpl.display_name))

                    sub = self._find_subfolder_for_code(service, main_id, code)
                    if not sub:
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
                    _logger.info("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive).")
                    raise UserError(_("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive)."))
                code = (tmpl.default_code or "").strip()
                if not code:
                    _logger.info("No está configurado el default_code para el producto '%s'." % tmpl.display_name)
                    raise UserError(_("No está configurado el default_code para el producto '%s'." % tmpl.display_name))

                sub = self._find_subfolder_for_code(service, main_id, code)
                if not sub:
                    _logger.info("No se encontró subcarpeta para el código '%s' dentro de la carpeta principal." % code)
                    raise UserError(_("No se encontró subcarpeta para el código '%s' dentro de la carpeta principal." % code))
                target_folder_id = sub["id"]
                root_prefix = (sub.get("name") or code).strip().replace("/", "_")   
            # Armar ZIP SOLO de esa subcarpeta
            mem = io.BytesIO()
            with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_STORED) as zipf:
                root_prefix = (sub.get("name") or code).strip().replace("/", "_")
                _walk_and_zip(zipf, sub["id"], root_prefix)
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
