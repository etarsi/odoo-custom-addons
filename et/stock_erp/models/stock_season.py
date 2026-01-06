# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StockSeason(models.Model):
    _name = "stock.season"
    _description = "Temporada de Stock"
    _order = "date_start desc, name"

    name = fields.Char(required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date()
    state = fields.Selection(
        [("draft", "Borrador"), ("done", "Activo"), ("closed", "Cerrado")],
        string="Estado",
        default="draft",
        required=True,
    )


class StockSeasonOpeningLine(models.Model):
    _name = "stock.season.opening.line"
    _description = "Stock Inicial por Temporada"
    _order = "season_id desc, product_tmpl_id"

    season_id = fields.Many2one("stock.season", required=True, index=True, ondelete="cascade")
    product_tmpl_id = fields.Many2one("product.template", required=True, index=True, ondelete="cascade")
    uxb = fields.Float(string="UXB (Unidades x Bulto)", default=0.0)
    bultos = fields.Float(string="Bultos", default=0.0)
    unidades_sueltas = fields.Float(string="Unidades sueltas", default=0.0)

    unidades_iniciales = fields.Float(
        string="Unidades iniciales",
        compute="_compute_unidades_iniciales",
        store=True,
    )

    @api.depends("uxb", "bultos", "unidades_sueltas")
    def _compute_unidades_iniciales(self):
        for rec in self:
            rec.unidades_iniciales = (rec.bultos or 0.0) * (rec.uxb or 0.0) + (rec.unidades_sueltas or 0.0)

    @api.constrains("uxb", "bultos", "unidades_sueltas")
    def _check_non_negative(self):
        for rec in self:
            if rec.uxb < 0 or rec.bultos < 0 or rec.unidades_sueltas < 0:
                raise ValidationError(_("UXB, Bultos y Unidades sueltas no pueden ser negativos."))

    _sql_constraints = [
        # Si agregás warehouse_id o location_id, sumalos a la constraint.
        ("season_product_company_uniq",
         "unique(season_id, product_tmpl_id, company_id)",
         "Ya existe un stock inicial para ese producto en esa temporada (y compañía)."),
    ]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    season_opening_line_ids = fields.One2many(
        "stock.season.opening.line",
        "product_tmpl_id",
        string="Stocks iniciales por temporada",
    )
