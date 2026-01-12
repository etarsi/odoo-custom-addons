# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StockSeason(models.Model):
    _name = "stock.season"
    _description = "Temporada de Stock"
    _order = "date_start desc, name"

    name = fields.Char(string="Descripción", required=True)
    date_start = fields.Date(string="Fecha Inicio", required=True)
    date_end = fields.Date(string="Fecha Fin", required=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("done", "Activo"), ("closed", "Cerrado")],
        string="Estado",
        default="draft",
        required=True,
    )


class StockSeasonLine(models.Model):
    _name = "stock.season.line"
    _description = "Stock Inicial por Temporada"
    _order = "season_id desc, product_id"

    season_id = fields.Many2one("stock.season", string="Temporada", required=True, index=True, ondelete="cascade")
    product_id = fields.Many2one("product.template", string="Producto", required=True, index=True, ondelete="cascade")
    bultos_inicial = fields.Float(string="Bultos", default=0.0)
    uxb = fields.Float(string="UXB (Unidades x Bulto)", default=0.0)
    unidades_inicial = fields.Float(string="Unidades", store=True, required=True)

    @api.depends("uxb", "bultos_inicial")
    def _compute_unidades_inicial(self):
        for rec in self:
            rec.unidades_inicial = (rec.bultos_inicial or 0.0) * (rec.uxb or 0.0)

    @api.constrains("uxb", "bultos_inicial")
    def _check_non_negative(self):
        for rec in self:
            if rec.uxb < 0 or rec.bultos_inicial < 0:
                raise ValidationError(_("UXB y Bultos no pueden ser negativos."))

class ProductTemplate(models.Model):
    _inherit = "product.template"

    season_line_ids = fields.One2many(
        "stock.season.line",
        "product_id",
        string="Stocks iniciales por temporada",
    )
