# -*- coding: utf-8 -*-
import io
import os
import base64
import logging
import zipfile
from datetime import datetime

from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

_logger = logging.getLogger(__name__)

# ---- Configuración básica ----
ALLOWED_IMAGE_MIMES = ("image/jpeg", "image/png")
ALLOWED_IMAGE_EXTS = (".jpg", ".jpeg", ".png")
# Ruta al JSON del service account (ajustá si preferís leer de ir.config_parameter)
SERVICE_ACCOUNT_JSON = "/opt/odoo15/drive-api/service_account.json"


# ==============================
# Helpers Google Drive
# ==============================
def _is_image(file_obj):
    mime = (file_obj.get("mimeType") or "").lower()
    name = (file_obj.get("name") or "").lower()
    return (mime in ALLOWED_IMAGE_MIMES) or name.endswith(ALLOWED_IMAGE_EXTS)


def _build_gdrive_service():
    """Crea el servicio de Google Drive (Service Account)."""
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _gdrive_list_folder_items(service, folder_id):
    """Lista archivos y subcarpetas dentro de 'folder_id'."""
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


def _gdrive_resolve_shortcut(service, file_obj):
    """Si es un atajo, resolver al destino real."""
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


def _find_subfolder_for_code(service, main_folder_id, code):
    """
    Busca una subcarpeta hija directa cuyo nombre:
      1) sea exactamente 'code', o
      2) empiece con 'code ' / 'code-' / 'code_', o
      3) contenga 'code'.
    Devuelve dict con {id, name, mimeType} o None.
    """
    code_str = (code or "").strip()
    if not code_str:
        return None

    code_escaped = code_str.replace("'", r"\'")
    q = (
        f"'{main_folder_id}' in parents and trashed=false "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and name contains '{code_escaped}'"
    )
    _logger.debug("Drive query (subcarpeta por código): %s", q)

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


def _zip_subfolder_images(service, folder_id, root_prefix):
    """Devuelve bytes de un ZIP con SOLO imágenes de la subcarpeta (recursivo)."""
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

    def _walk_and_zip(zipf, current_folder_id, prefix):
        items = _gdrive_list_folder_items(service, current_folder_id)
        for it in items:
            it = _gdrive_resolve_shortcut(service, it)
            mime = it.get("mimeType")
            name = it.get("name") or it["id"]
            if mime == "application/vnd.google-apps.folder":
                sub_prefix = f"{prefix}/{name}" if prefix else name
                # Entrada de directorio (opcional)
                zinfo = zipfile.ZipInfo(f"{sub_prefix}/")
                zipf.writestr(zinfo, b"")
                _walk_and_zip(zipf, it["id"], sub_prefix)
            else:
                if _is_image(it):
                    _add_file_to_zip(zipf, it, prefix)

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
        _walk_and_zip(zipf, folder_id, root_prefix)
    mem.seek(0)
    return mem.read()


# ==============================
# Controller
# ==============================
class ProductImageDownloadController(http.Controller):

    @http.route(['/shop/product/<model("product.template"):product>/download-images-zip'],
                type='http', auth='public', website=True, methods=['GET'], csrf=False)
    def product_download_images_zip(self, product, **kw):
        """Genera un ZIP por default_code desde la carpeta principal del producto y redirige a su descarga."""
        # Sólo productos publicados
        if not product.website_published:
            return request.not_found()

        # Sudo para evitar problemas de permisos (crear adjuntos/leer params)
        product = product.sudo()

        # Validaciones de datos del producto
        main_id = ("1Mob5cI20nki0GayprUS4d2g-Q1KmEXJg").strip()
        if not main_id:
            return request.render('website.404', {'error_message': _("El producto no tiene configurado el Google Drive Folder ID.")})
        code = (product.default_code or "").strip()
        if not code:
            return request.render('website.404', {'error_message': _("El producto no tiene default_code (Referencia interna).")})

        # Servicio Drive
        try:
            service = _build_gdrive_service()
        except Exception as e:
            _logger.exception("Error construyendo servicio de Drive")
            return request.render('website.404', {'error_message': _("Error con Google Drive: %s") % e})

        # Buscar subcarpeta por código
        try:
            sub = _find_subfolder_for_code(service, main_id, code)
        except Exception as e:
            _logger.exception("Error buscando subcarpeta en Drive")
            return request.render('website.404', {'error_message': _("Error buscando subcarpeta: %s") % e})

        if not sub:
            return request.render('website.404', {'error_message': _("No se encontró subcarpeta '%s' dentro de la carpeta principal.") % code})

        # Armar ZIP SOLO de esa subcarpeta
        try:
            root_prefix = (sub.get("name") or code).strip().replace("/", "_")
            zip_bytes = _zip_subfolder_images(service, sub["id"], root_prefix)
        except Exception as e:
            _logger.exception("Error generando ZIP")
            return request.render('website.404', {'error_message': _("Error generando ZIP: %s") % e})

        if not zip_bytes:
            return request.render('website.404', {'error_message': _("No se encontraron imágenes para comprimir.")})

        # Crear adjunto y generar token
        try:
            zip_name = f"{(product.name or code).strip().replace('/', '_')}_{code}_images.zip"
            att = request.env['ir.attachment'].sudo().create({
                "name": zip_name,
                "datas": base64.b64encode(zip_bytes),
                "res_model": product._name,
                "res_id": product.id,
                "mimetype": "application/zip",
            })
            # Generar access_token para descarga pública
            if not att.access_token:
                att.generate_access_token()
        except Exception as e:
            _logger.exception("Error creando adjunto")
            return request.render('website.404', {'error_message': _("Error creando adjunto: %s") % e})

        # Redirigir a descarga con token
        url = f"/web/content/{att.id}?download=1"
        return request.redirect(url)
