# -*- coding: utf-8 -*-
import base64
import io
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GOOGLE_IMPORT_HINT = _(
    "Faltan dependencias de Google API. Instalá en el servidor:\n"
    "  pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib\n"
)

class ProductImage(models.Model):
    _inherit = "product.image"

    # Guardamos el fileId de Drive para evitar duplicados
    gdrive_file_id = fields.Char(index=True)

    _sql_constraints = [
        # Evita duplicar la misma imagen de Drive para el mismo template
        ("gdrive_unique_per_tmpl", "unique(gdrive_file_id, product_tmpl_id)",
         "Esta imagen de Google Drive ya está asociada a este producto."),
    ]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    gdrive_folder_id = fields.Char(
        string="Google Drive Folder ID",
        help="ID de la carpeta en Drive con las imágenes del producto."
    )

    def action_open_gallery(self):
        """Abre la galería (product.image) filtrada por este producto."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Galería de Imágenes"),
            "res_model": "product.image",
            "view_mode": "kanban,tree,form",
            "domain": [("product_tmpl_id", "=", self.id)],
            "context": {"default_product_tmpl_id": self.id},
            "target": "current",
        }

    def action_download_images_from_drive(self):
        """Descarga imágenes desde la carpeta de Drive gdrive_folder_id a product.image."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload
        except Exception as e:
            raise UserError(GOOGLE_IMPORT_HINT + "\n\n" + str(e))

        params = self.env["ir.config_parameter"].sudo()

        # Ruta al JSON del service account (guardalo como parámetro del sistema)
        sa_path = params.get_param("gdrive.service_account_file")  # ej: /opt/keys/service_account.json
        if not sa_path:
            raise UserError(
                _("Configurá el parámetro del sistema 'gdrive.service_account_file' con la ruta al JSON del Service Account.")
            )

        # Opcional: impersonación (si compartís la carpeta con el SA y necesitás actuar como un usuario)
        delegated_user = params.get_param("gdrive.delegated_user") or None

        scopes = ["https://www.googleapis.com/auth/drive.readonly"]

        try:
            if delegated_user:
                creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
                creds = creds.with_subject(delegated_user)
            else:
                creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
        except Exception as e:
            raise UserError(_("No se pudo cargar el Service Account.\n%s") % e)

        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        for tmpl in self:
            folder_id = (tmpl.gdrive_folder_id or "").strip()
            if not folder_id:
                raise UserError(_("El producto '%s' no tiene configurado el Google Drive Folder ID.") % tmpl.display_name)

            # Listamos imágenes dentro de la carpeta
            q = (
                f"'{folder_id}' in parents and trashed=false and "
                f"(mimeType contains 'image/' or mimeType='application/octet-stream')"
            )

            page_token = None
            created = 0
            skipped = 0

            while True:
                resp = service.files().list(
                    q=q,
                    pageSize=1000,
                    pageToken=page_token,
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)"
                ).execute()

                for f in resp.get("files", []):
                    file_id = f["id"]
                    name = f.get("name") or file_id

                    # Si ya existe por gdrive_file_id + product_tmpl_id, saltamos
                    exists = self.env["product.image"].search_count([
                        ("gdrive_file_id", "=", file_id),
                        ("product_tmpl_id", "=", tmpl.id),
                    ])
                    if exists:
                        skipped += 1
                        continue

                    # Descargar binario
                    request = service.files().get_media(fileId=file_id)
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    try:
                        while not done:
                            status, done = downloader.next_chunk()
                    except Exception as e:
                        _logger.exception("Error descargando %s (%s): %s", name, file_id, e)
                        continue

                    data = fh.getvalue()
                    if not data:
                        _logger.warning("Archivo vacío: %s (%s)", name, file_id)
                        continue

                    # Crear product.image
                    self.env["product.image"].create({
                        "name": name,
                        "product_tmpl_id": tmpl.id,
                        "image_1920": base64.b64encode(data),
                        "gdrive_file_id": file_id,
                    })
                    created += 1

                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

            msg = _("Descarga de Drive completada para '%s': %s creadas, %s omitidas (duplicadas).") % (
                tmpl.display_name, created, skipped
            )
            _logger.info(msg)

        return True
