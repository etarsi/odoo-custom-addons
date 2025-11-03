from odoo import models, fields, api, _


class ProductDownloadMark(models.Model):

    _name = "product.download.mark"
    _description = "Product Download Mark"

    product_id = fields.Many2one("product.template", string="Producto", required=True)
    download_mark = fields.Boolean(string="Marca de Descarga", default=False)
    description = fields.Text(string="Descripcion")
    date = fields.Datetime(string="Fecha de Intento", default=fields.Datetime.now)
    

    