# -*- coding: utf-8 -*-
import logging, json
from odoo import models, _
from google.oauth2 import service_account
from googleapiclient.discovery import build

_logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

class WmsGoogleSheetsClient(models.AbstractModel):
    _name = "wms.google.sheets.client"
    _description = "WMS Google Sheets Client"

    def _svc(self, sa_json_path):
        creds = service_account.Credentials.from_service_account_file(sa_json_path, scopes=SCOPES)
        return build("sheets", "v4", credentials=creds)

    def _title_from_gid(self, svc, spreadsheet_id, gid):
        meta = svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for sh in meta.get("sheets", []):
            if sh["properties"]["sheetId"] == int(gid):
                return sh["properties"]["title"]
        raise ValueError(_("No encontré pestaña con gid=%s") % gid)

    def append_row(self, values):
        """Agrega una fila al final. 'values' debe ser una lista."""
        config_parameters = self.env["ir.config_parameter"].sudo()
        sheet_enable = config_parameters.get_param("stock_enhancement2.sheet_enable")
        sheet_spreadsheet_id = config_parameters.get_param("stock_enhancement2.sheet_spreadsheet_id")
        sheet_gid = config_parameters.get_param("stock_enhancement2.sheet_gid")
        sa_path = "/opt/odoo15/drive-api/service_account.json"  # Ruta fija del JSON del servicio
        if not sheet_enable:
            return False
        svc = self._svc(sa_path)
        title = self._title_from_gid(svc, sheet_spreadsheet_id, sheet_gid)
        rng = f"{title}!A:Z"  # empieza siempre en B
        body = {"values": [values]}
        resp = svc.spreadsheets().values().append(
            spreadsheetId=sheet_spreadsheet_id,
            range=rng,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
        updated = resp.get("updates", {}).get("updatedRange")
        _logger.info("Sheets append OK: %s", updated)
        return 200 if updated else 0