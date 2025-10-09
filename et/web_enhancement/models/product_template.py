# -*- coding: utf-8 -*-
import io
import os
import base64
import logging
import zipfile
from datetime import datetime

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

class ProductTemplate(models.Model):
    _inherit = "product.template"

    gdrive_folder_id = fields.Char(
        string="Google Drive Folder ID",
        help="ID de la carpeta PRINCIPAL en Drive. Dentro habrá subcarpetas por default_code.",
    )

    # --------- Google Drive helpers ---------
    def _build_gdrive_service(self):
        sa_path = "/opt/odoo15/drive-api/service_account.json"  # tu ruta fija
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
        Busca una subcarpeta bajo 'main_folder_id' cuyo nombre:
        1) sea exactamente 'code', o
        2) empiece con 'code ' / 'code-' / 'code_', o
        3) contenga 'code'.
        Devuelve el dict del folder elegido o None.
        """
        code_str = (code or "").strip()
        if not code_str:
            return None

        # ESCAPAR comillas simples en el nombre para la query de Drive
        code_escaped = code_str.replace("'", r"\'")

        # IMPORTANTE: el folder_id debe ir ENTRE COMILLAS en la query
        q = (
            f"'{main_folder_id}' in parents and trashed=false "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and name contains '{code_escaped}'"
        )
        _logger.debug("Drive list (buscando subcarpeta por código) q=%s", q)

        folders = []
        page_token = None
        while True:
            resp = service.files().list(
                q=q,
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            folders.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        if not folders:
            return None

        # Scoring: exact == 3, startswith == 2, contains == 1; luego por nombre más corto
        def score(f):
            name = (f.get("name") or "").strip()
            if name == code_str:
                return (3, -len(name))
            if name.lower().startswith((code_str + " ").lower()) \
            or name.lower().startswith((code_str + "-").lower()) \
            or name.lower().startswith((code_str + "_").lower()):
                return (2, -len(name))
            return (1, -len(name))

        folders.sort(key=score, reverse=True)
        best = folders[0]
        if best and (best.get("name") or "").strip() != code_str:
            _logger.info("Subcarpeta elegida por coincidencia parcial: %s (code=%s)", best.get("name"), code_str)
        return best

    # --------- Acción: ZIP por default_code ---------
    def action_zip_by_default_code_from_main_folder(self):
        """
        Para cada producto:
          - Usa gdrive_folder_id como CARPETA PRINCIPAL.
          - Busca subcarpeta cuyo nombre coincida con default_code (exacto/empieza/contiene).
          - Zipea SOLO esa subcarpeta (recursivo), guardando solo imágenes (.jpg/.jpeg/.png).
          - Crea ir.attachment y devuelve descarga directa (si es un producto).
        """
        service = self._build_gdrive_service()
        attachments = []
        sheet_drive_folder_path = self.env['ir.config_parameter'].get_param('web_enhancement.sheet_drive_folder_path')
        if not sheet_drive_folder_path:
            raise UserError(_("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive)."))
        
        def _add_file_to_zip(zipf, file_obj, arc_prefix):
            file_id = file_obj["id"]
            file_name = file_obj.get("name") or file_id
            buf = io.BytesIO()
            req = service.files().get_media(fileId=file_id)
            downloader = MediaIoBaseDownload(buf, req)
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
                        raise UserError(_("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive)."))
                    code = (tmpl.default_code or "").strip()
                    if not code:
                        raise UserError(_("El producto '%s' no tiene default_code (Referencia interna).") % tmpl.display_name)

                    sub = self._find_subfolder_for_code(service, main_id, code)
                    if not sub:
                        raise UserError(_("No se encontró subcarpeta para el código '%s' dentro de la carpeta principal.") % code)
                    target_folder_id = sub["id"]
                    root_prefix = (sub.get("name") or code).strip().replace("/", "_")
                else:
                    target_folder_id = sub["id"]
                    root_prefix = (sub.get("name") or tmpl.default_code or f"product_{tmpl.id}").strip().replace("/", "_")
            else:
                # Caso 2: usar carpeta principal global y buscar subcarpeta por default_code
                main_id = (sheet_drive_folder_path or "").strip()
                if not main_id:
                    raise UserError(_("No está configurado el ID de la carpeta principal en Drive (Settings > Configuración de Google Drive)."))
                code = (tmpl.default_code or "").strip()
                if not code:
                    raise UserError(_("El producto '%s' no tiene default_code (Referencia interna).") % tmpl.display_name)

                sub = self._find_subfolder_for_code(service, main_id, code)
                if not sub:
                    raise UserError(_("No se encontró subcarpeta para el código '%s' dentro de la carpeta principal.") % code)
                target_folder_id = sub["id"]
                root_prefix = (sub.get("name") or code).strip().replace("/", "_")   
            # Armar ZIP SOLO de esa subcarpeta
            mem = io.BytesIO()
            with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
                root_prefix = (sub.get("name") or code).strip().replace("/", "_")
                _walk_and_zip(zipf, sub["id"], root_prefix)
            mem.seek(0)
            data_b64 = base64.b64encode(mem.read())
            zip_name = f"{(tmpl.name or code).strip().replace('/', '_')}_{code}_imagenes.zip"

            attach = self.env["ir.attachment"].create({
                "name": zip_name,
                "datas": data_b64,
                "res_model": tmpl._name,
                "res_id": tmpl.id,
                "mimetype": "application/zip",
            })
            #generar token si no tiene
            if not attach.access_token:
                attach._generate_access_token()
            attachments.append(attach.id)
            _logger.info("ZIP creado para '%s' (subcarpeta '%s') -> attachment id %s",
                         tmpl.display_name, sub.get("name"), attach.id)
            #guardar el id en el campo del producto
            tmpl.write({'gdrive_folder_id': target_folder_id})
        _logger.info("Total productos procesados: %d", len(self))
        _logger.info("Total attachments creados: %d", len(attachments))
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
