# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TmsRoadmap(models.Model):
    _name = "tms.roadmap"
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    _description = "Hoja de Ruta"
    _order = "date desc, id desc"

    name = fields.Char(string="Número", required=True, copy=False, index=True, default=lambda self: _("New"), tracking=True)
    date = fields.Datetime(string="Fecha", required=True, default=fields.Datetime.now, index=True)
    transport_id = fields.Many2one("tms.transport", string="Vehículo", index=True, tracking=True, ondelete="set null")
    patente = fields.Char(string="Patente", tracking=True)
    area = fields.Selection(string="Área", selection=[
        ("pg", "Pedidos Generales"),
        ("gc", "Grandes Cadenas"),
        ("millan", "Millan"),
        ("other", "Otro"),
    ], required=True, default="pg", tracking=True)
    observations = fields.Text(string="Observaciones", tracking=True)
    total_bulto_defendant = fields.Float(string="T. Bultos Demandados", tracking=True)
    total_bulto_picking = fields.Float(string="T. Bultos Pickeados", tracking=True)
    total_lvl_compliance = fields.Float(string="T. Nivel de Cumplimiento", compute="_compute_total_lvl_compliance", store=True, tracking=True)
    citation_id = fields.Many2one("tms.citation", string="Citación", ondelete="set null", index=True, tracking=True)
    citation_count = fields.Integer(string="Número de Citaciones", compute="_compute_citation_count", store=False, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("pending", "Pendiente"),
            ("completed", "Completada"),
            ("canceled", "Cancelada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    assistants = fields.Integer(string="Ayudantes", store=True, tracking=True)
    in_ruta = fields.Integer(string="C, Indice de Vuelta-Ruta", store=True, tracking=True)
    type_roadmap = fields.Selection(string="Tipo", selection=[
        ("delivery", "Entrega"),
        ("pickup", "Retiro"),
    ], required=True, default="delivery", tracking=True)
    tms_stock_picking_id = fields.Many2one(
        "tms.stock.picking",
        string="Ruteo Asociado",
        required=False,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    industry_ids = fields.Many2many("res.partner.industry", string="Zonas", compute="_compute_industry_ids", store=True, tracking=True)
    road_maps_line_ids = fields.One2many("tms.roadmap.line", "roadmap_id", string="Líneas de Hoja de Ruta", tracking=True)
    
    #SQL
    _sql_constraints = [
        ("uniq_tms_roadmap_name", "unique(name)", "La referencia de Hoja de Ruta debe ser única."),
    ]

    def _compute_industry_ids(self):
        for rec in self:
            industry_ids = rec.road_maps_line_ids.mapped('industry_id').ids
            rec.industry_ids = [(6, 0, industry_ids)]


    def _compute_citation_count(self):
        for rec in self:
            rec.citation_count = 1 if rec.citation_id else 0

    @api.depends("total_bulto_defendant", "total_bulto_picking")
    def _compute_total_lvl_compliance(self):
        for rec in self:
            denom = rec.total_bulto_defendant or 0.0
            num = rec.total_bulto_picking or 0.0
            if denom > 0.0:
                pct = (num / denom) * 100.0
                rec.total_lvl_compliance = min(pct, 100.0)  # tope 100%
            else:
                rec.total_lvl_compliance = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("tms.roadmap") or _("New")
        return super().create(vals_list)
    
    @api.onchange("transport_id")
    def _onchange_transport_id(self):
        if self.transport_id:
            if self.transport_id.patente_trc:
                self.patente = self.transport_id.patente_trc
            if self.transport_id.patente_semi:
                self.patente = self.transport_id.patente_semi
        else:
            self.patente = False
            
    def action_open_citation(self):
        self.ensure_one()
        if not self.citation_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": _("Citación"),
            "res_model": "tms.citation",
            "view_mode": "form",
            "res_id": self.citation_id.id,
            "target": "current",
        }
        
    def action_unlink_roadmap(self):
        for rec in self:
            rec.citation_id = False
        return True
    
    
    
class TmsRoadmapLine(models.Model):
    _name = "tms.roadmap.line"
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    _description = "Hoja de Ruta Línea"
    _order = "date desc, id desc"

    name = fields.Char(string="Etiqueta", required=True, copy=False, index=True, default=lambda self: _("New"), tracking=True)
    date = fields.Datetime(string="Fecha", required=True, default=fields.Datetime.now, index=True)
    transport_id = fields.Many2one("tms.transport", string="Vehículo", index=True, tracking=True, ondelete="set null")
    patente = fields.Char(string="Patente", tracking=True)
    bulto_defendant = fields.Float(string="Bultos Demandados", tracking=True)
    bulto_picking = fields.Float(string="Bultos Pickeados", tracking=True)
    lvl_compliance = fields.Float(string="Nivel de Cumplimiento", compute="_compute_lvl_compliance", store=True, tracking=True)
    state = fields.Selection(
        related="roadmap_id.state",
        string="Estado",
        store=True,
        readonly=True,
        tracking=True,
        index=True,
    )
    in_ruta = fields.Integer(string="Indice de Vuelta-Ruta", store=True, tracking=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", store=True, tracking=True)
    direction = fields.Char(string="Dirección", store=True, tracking=True)
    type_roadmap = fields.Selection(string="Tipo", selection=[
        ("delivery", "Entrega"),
        ("pickup", "Retiro"),
    ], required=True, default="delivery", tracking=True)
    tms_stock_picking_id = fields.Many2one(
        "tms.stock.picking",
        string="Ruteo Asociado",
        required=False,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    industry_id = fields.Many2one("res.partner.industry", string="Zona", store=True, tracking=True, related='partner_id.industry_id')
    roadmap_id = fields.Many2one("tms.roadmap", string="Hoja de Ruta Principal", ondelete="cascade", index=True, tracking=True)
    


    @api.depends("bulto_defendant", "bulto_picking")
    def _compute_lvl_compliance(self):
        for rec in self:
            if rec.bulto_defendant > 0 and rec.bulto_picking > 0:
                rec.lvl_compliance = (rec.bulto_picking / rec.bulto_defendant) * 100
            else:
                rec.lvl_compliance = 0.0
    
    @api.onchange("transport_id")
    def _onchange_transport_id(self):
        if self.transport_id:
            if self.transport_id.patente_trc:
                self.patente = self.transport_id.patente_trc
            if self.transport_id.patente_semi:
                self.patente = self.transport_id.patente_semi
        else:
            self.patente = False