# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TmsCitation(models.Model):
    _name = "tms.citation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Ruteo Citación"
    _order = "date desc, id desc"

    name = fields.Char(string="Referencia", required=True, copy=False, index=True, default=lambda self: _("New"), tracking=True)
    tms_roadmap_ids = fields.One2many("tms.roadmap", "citation_id", string="Hojas de Rutas", index=True, tracking=True)
    date = fields.Datetime(string="Fecha", required=True, default=fields.Datetime.now, index=True, tracking=True)
    mes = fields.Char(string="Mes", compute="_compute_mes", store=True, index=True, tracking=True)
    empresa_id = fields.Many2one("delivery.carrier", string="Empresa", required=True, index=True, tracking=True)
    transport_id = fields.Many2one("tms.transport", string="Vehículo", required=True, index=True, tracking=True)
    transport_type_id = fields.Many2one("tms.transport.type", string="Tipo de Vehículo", required=True, tracking=True)
    patente_tractor = fields.Char(string="Patente Tractor", tracking=True)
    patente_semi = fields.Char(string="Patente Semi", tracking=True)
    service_id = fields.Many2one("tms.service", string="Servicio", required=True, index=True, tracking=True)
    area = fields.Selection(string="Área", selection=[
        ("pg", "Pedidos Generales"),
        ("gc", "Grandes Cadenas"),
        ("millan", "Millan"),
        ("other", "Otro"),
    ], required=True, default="pg", tracking=True)
    # Para mostrarlo lindo en UI, después en la vista usás widget="float_time"
    hour_citation = fields.Float(string="Hora Citación", required=True, tracking=True)
    hour_arrival = fields.Float(string="Hora Llegada", tracking=True)
    hiring_id = fields.Many2one("tms.hiring", string="Contratación", required=True, tracking=True)
    observations = fields.Text(string="Observaciones", tracking=True)
    # En la planilla 'Btos G.C' viene con decimales (ej 35.67), por eso Float.
    bulto_count = fields.Float(string="Cantidad de Bultos", tracking=True)
    tms_stock_picking_id = fields.Many2one(
        "tms.stock.picking",
        string="Remito Asociado",
        required=False,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
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

    @api.depends("date")
    def _compute_mes(self):
        for rec in self:
            if rec.date:
                d = fields.Datetime.to_datetime(rec.date)
                rec.mes = f"{d.month:02d}/{d.year}"
            else:
                rec.mes = False

    @api.constrains("hour_citation", "hour_arrival")
    def _check_hours(self):
        for rec in self:
            for fname in ("hour_citation", "hour_arrival"):
                v = rec[fname]
                if v is not False and v is not None and (v < 0.0 or v >= 24.0):
                    raise ValidationError(_("La hora debe estar entre 0 y 24."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("tms.citation") or _("New")
        return super().create(vals_list)
    


class TmsRoadmap(models.Model):
    _name = "tms.roadmap"
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    _description = "Hoja de Ruta"
    _order = "date desc, id desc"

    name = fields.Char(string="Referencia", required=True, copy=False, index=True, default=lambda self: _("New"), tracking=True)
    date = fields.Datetime(string="Fecha", required=True, default=fields.Datetime.now, index=True)
    transport_id = fields.Many2one("tms.transport", string="Vehículo", required=True, index=True, tracking=True)
    patente = fields.Char(string="Patente", tracking=True)
    area = fields.Selection(string="Área", selection=[
        ("pg", "Pedidos Generales"),
        ("gc", "Grandes Cadenas"),
        ("millan", "Millan"),
        ("other", "Otro"),
    ], required=True, default="pg", tracking=True)
    hiring_id = fields.Many2one("tms.hiring", string="Contratación", required=True, tracking=True)
    observations = fields.Text(string="Observaciones", tracking=True)
    bulto_count = fields.Float(string="Bultos", tracking=True)
    bulto_count_verified = fields.Float(string="Bultos Verificados", tracking=True)
    citation_id = fields.Many2one("tms.citation", string="Citación", ondelete="set null", index=True, tracking=True)
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
    in_ruta = fields.Integer(string="Indice de Vuelta-Ruta", store=True, tracking=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", store=True, tracking=True)
    direction = fields.Char(string="Dirección", store=True, tracking=True)


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("tms.roadmap") or _("New")
        return super().create(vals_list)