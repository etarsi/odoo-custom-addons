from odoo import tools, models, fields, api, _
import base64
import logging
import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account

_logger = logging.getLogger(__name__)


class CatalogoPedido(models.Model):
    _name = "sebigus.catalogo.pedido"
    # _inherit = ["mail.thread", "mail.activity.mixin", "image.mixin"]
    _description = "Catalogo Pedido Online"
    name = fields.Char(string="Name")
    fecha = fields.Date(string="Fecha")
    categoria = fields.Many2one("product.brand", string="Categoria")
    partner_id = fields.Many2one("res.partner", string="Empresa", required=True)
    spreadsheet_id = fields.Char(string="Google ID")
    nombre_archivo = fields.Char(string="Nombre Archivo")

    def generar(self):
        self.nombre_archivo = "%s %s" % (self.partner_id.name, self.categoria.name)
        productos = {}
        for p in self.env["product.template"].search(
            [("product_brand_id", "=", self.categoria.id)]
        ):
            productos[p.default_code] = p
        prods = {}
        for pp in productos:
            p = productos[pp]
            try:
                prods[
                    "%-20s_%s" % (p.public_categ_ids[0].name.strip(), p.default_code)
                ] = p
            except:
                continue

        stock_actual = {}
        quants = self.env["stock.quant"].sudo().search([("location_id", "=", 8)])
        for q in quants:
            stock_actual[q.product_id.id] = q[0].available_quantity
        data_tmp = []
        data = []
        cat_id = 0
        for pp in sorted(prods):
            p = prods[pp]
            if p.public_categ_ids and p.public_categ_ids[0].id != cat_id:
                _logger.info("CATEGORIA %s %s" % (self.categoria.id, pp))
                try:
                    categoria = p.public_categ_ids[0]
                    cat_id = p.public_categ_ids[0].id
                except:
                    continue
                # Cuando cambio de categoria ordeno por precio
                if len(data_tmp) > 0:
                    newlist = sorted(data_tmp, key=lambda d: d["Precio"])
                    data_tmp = []
                    data.append(titulos_seccion)
                    data = data + newlist
                det = {}
                det["DT_RowId"] = "categoria"
                if categoria.image_1920:
                    imagen = (
                        '=image("https://ventas.sebigus.com.ar/web/image/product.public.category/%s/image_1920")'
                        % p.public_categ_ids[0].id
                    )
                    det["Descripcion"] = imagen
                else:
                    det["Descripcion"] = "%s" % p.public_categ_ids[0].name
                det["Codigo"] = "  "
                det["Imagen"] = " "
                det["Dimensiones"] = " "
                det["Bulto"] = " "
                det["Precio"] = " "
                det["Pedido"] = " "
                det["Unidades_Pedidas"] = p.public_categ_ids[0].name
                det["Stock"] = " "
                det["Stock_Sugeridos"] = " "
                titulos_seccion = det
                # data.append(det)
            det = {}
            det["DT_RowId"] = "row_%s" % p.default_code
            imagen = (
                '=image("https://ventas.sebigus.com.ar/web/image/product.product/%s/image_128")'
                % p.id
            )
            det["Imagen"] = imagen
            det["Codigo"] = p.default_code
            det["Descripcion"] = p.name
            det["Dimensiones"] = p.description_sale if p.description_sale else " "
            det["Bulto"] = "%d" % p.uom_po_id.ratio
            det["Precio"] = p.list_price
            # quants = request.env['stock.quant'].sudo().search([('product_id','=',p.id),('location_id','=',8)])
            quants = stock_actual[p.id] if p.id in stock_actual else None
            det["Pedido"] = ""
            if p.list_price > 1:
                data_tmp.append(det)
        if len(data_tmp) > 0:
            newlist = sorted(data_tmp, key=lambda d: d["Precio"])
            data.append(titulos_seccion)
            data = data + newlist
        _logger.info("TIEMPO Tabla")

        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        KEY = "/opt/odoo16/16.0/extra-addons/sebigus/static/sebigus-preventa-55f0f156ceb2.json"
        MODELO_ID = "1-gn5TmIinyOhZ5Mw78ySXcVq5lGWTx_daWefnlvT3XA"
        FOLDER_ID = "1o9e104FNL-Juh6ZFcq4I-arSQFeySpOV"

        creds = service_account.Credentials.from_service_account_file(
            KEY, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=creds)
        srv_drive = build("drive", "v3", credentials=creds)
        if not self.spreadsheet_id:
            new_file = (
                srv_drive.files()
                .copy(
                    fileId=MODELO_ID,
                    body={"parents": [FOLDER_ID], "name": self.nombre_archivo},
                )
                .execute()
            )
            self.spreadsheet_id = new_file["id"]
            destino = {"destinationSpreadsheetId": self.spreadsheet_id}
            sheet_id = 0
            request = (
                service.spreadsheets()
                .sheets()
                .copyTo(spreadsheetId=MODELO_ID, sheetId=sheet_id, body=destino)
                .execute()
            )
            sheet_id = request["sheetId"]
            rename = {
                "requests": {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "title": "Catalogo",
                        },
                        "fields": "title",
                    }
                }
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body=rename
            ).execute()
            sheets = (
                service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            )
            for ss in sheets["sheets"]:
                if ss["properties"]["title"] != "Catalogo":
                    delete = {
                        "requests": [
                            {"deleteSheet": {"sheetId": ss["properties"]["sheetId"]}}
                        ]
                    }
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=self.spreadsheet_id, body=delete
                    ).execute()
        data_c = []
        for d in data:
            data_c.append(
                [
                    d["Codigo"],
                    d["Imagen"],
                    d["Descripcion"],
                    d["Dimensiones"],
                    d["Bulto"],
                    d["Precio"],
                ]
            )
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range="C1",
                valueInputOption="USER_ENTERED",
                body={"values": [[self.partner_id.name]]},
            )
            .execute()
        )
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range="C2",
                valueInputOption="USER_ENTERED",
                body={"values": [[self.partner_id.sale_discount]]},
            )
            .execute()
        )
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range="C3",
                valueInputOption="USER_ENTERED",
                body={"values": [[self.partner_id.property_payment_term_id.name]]},
            )
            .execute()
        )
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range="A6",
                valueInputOption="USER_ENTERED",
                body={"values": data_c},
            )
            .execute()
        )
        # Cambio permisos y comparto el catalogo
        import gspread

        gc = gspread.service_account(
            filename="/opt/odoo16/16.0/extra-addons/sebigus/static/sebigus-preventa-55f0f156ceb2.json"
        )
        sheet = gc.open(self.nombre_archivo)
        sheetId = sheet.worksheet('Catalogo')
        body = {
            "requests": [
                {
                    "addProtectedRange": {
                        "protectedRange": {
                            "range": {"sheetId": sheetId},
                            "unprotectedRanges": [
                                {
                                    "sheetId": sheetId,
                                    "startRowIndex": 0,
                                    "endRowIndex": 5000,
                                    "startColumnIndex": 6,
                                    "endColumnIndex": 100,
                                }
                            ],
                            "editors": {
                                "domainUsersCanEdit": False,
                                "users": ["javierpepe@gmail.com"],
                            },
                            "warningOnly": False,
                        }
                    }
                }
            ]
        }
        sheet.batch_update(body)
        #sheet.('javierpepe@sysprinter.com.ar',perm_type='user',role='writer')



class CatalogoWizard(models.TransientModel):
    _name = "sebigus.catalogo.wizard"
    categoria = fields.Many2one("product.brand", string="Categoria")

    def generar_catalogo(self):
        # Por cada partner genero un catalogo
        for record in self._context.get("active_ids"):
            vars = {}
            vars["partner_id"] = record
            vars["categoria"] = self.categoria.id
            catalogo = self.env["sebigus.catalogo.pedido"].create(vars)
            catalogo.generar()
