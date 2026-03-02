# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TmsCitation(models.Model):
    _name = "tms.citation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Ruteo Citación"
    _order = "date desc, id desc"

    name = fields.Char(string="Número", required=True, copy=False, index=True, default=lambda self: _("New"), tracking=True)
    tms_roadmap_ids = fields.One2many("tms.roadmap", "citation_id", string="Hojas de Rutas", index=True, tracking=True)
    date = fields.Datetime(string="Fecha", required=True, default=fields.Datetime.now, index=True, tracking=True)
    mes = fields.Char(string="Mes", compute="_compute_mes", store=True, index=True, tracking=True)
    empresa_id = fields.Many2one("delivery.carrier", string="Empresa", domain="[('active', '=', True)]", required=True, index=True, tracking=True)
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
    total_bulk = fields.Float(string="T. Cantidad de Bultos", compute="_compute_total_bulto", tracking=True)
    total_bulk_verified = fields.Float(string="T. Cantidad de Bultos Verificados", compute="_compute_total_bulto_verified", tracking=True)
    percentage_verified = fields.Float(string="Porcentaje Verificado", compute="_compute_percentage_verified", store=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("pending", "Pendiente"),
            ("completed", "Completado"),
            ("canceled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    
    @api.depends("tms_roadmap_ids.bulto_count")
    def _compute_total_bulto(self):
        for rec in self:
            rec.total_bulk = sum(rec.tms_roadmap_ids.mapped('bulto_count'))   

    @api.depends("tms_roadmap_ids.bulto_count_verified")
    def _compute_total_bulto_verified(self):
        for rec in self:
            rec.total_bulk_verified = sum(rec.tms_roadmap_ids.mapped('bulto_count_verified'))

    @api.depends("total_bulk", "total_bulk_verified")
    def _compute_percentage_verified(self):
        for rec in self:
            if rec.total_bulk > 0 and rec.total_bulk_verified > 0:
                rec.percentage_verified = (rec.total_bulk_verified / rec.total_bulk) * 100
            else:
                rec.percentage_verified = 0.0
    

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
    
    @api.onchange("transport_id")
    def _onchange_transport_id(self):
        if self.transport_id:
            self.transport_type_id = self.transport_id.transport_type_id
            self.patente_tractor = self.transport_id.patente_trc
            self.patente_semi = self.transport_id.patente_semi
        else:
            self.transport_type_id = False
            self.patente_tractor = False
            self.patente_semi = False

    def action_post(self):
        for rec in self:
            if rec.state != "draft":
                raise ValidationError(_("Solo se pueden publicar hojas de ruta en estado Borrador."))
            rec.state = "pending"
            
    def action_draft(self):
        for rec in self:
            if rec.state != "pending":
                raise ValidationError(_("Solo se pueden volver a borrador hojas de ruta en estado Pendiente."))
            rec.state = "draft"
            
    def action_cancel(self):
        for rec in self:
            if rec.state == "canceled":
                raise ValidationError(_("La hoja de ruta ya está cancelada."))
            rec.state = "canceled"
            
    def action_completed(self):
        for rec in self:
            if rec.state != "pending":
                raise ValidationError(_("Solo se pueden completar hojas de ruta en estado Pendiente."))
            rec.state = "completed"



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
    bulto_count = fields.Float(string="Bultos", tracking=True)
    bulto_count_verified = fields.Float(string="Bultos Verificados", tracking=True)
    percentage_verified = fields.Float(string="Porcentaje Verificado", compute="_compute_percentage_verified", store=True, tracking=True)
    citation_id = fields.Many2one("tms.citation", string="Citación", ondelete="set null", index=True, tracking=True)
    citation_count = fields.Integer(string="Número de Citaciones", compute="_compute_citation_count", store=True, tracking=True)
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
    
    #SQL
    _sql_constraints = [
        ("uniq_tms_roadmap_name", "unique(name)", "La referencia de Hoja de Ruta debe ser única."),
    ]

    def _compute_citation_count(self):
        for rec in self:
            rec.citation_count = 1 if rec.citation_id else 0

    @api.depends("bulto_count", "bulto_count_verified")
    def _compute_percentage_verified(self):
        for rec in self:
            if rec.bulto_count > 0 and rec.bulto_count_verified > 0:
                rec.percentage_verified = (rec.bulto_count_verified / rec.bulto_count) * 100
            else:
                rec.percentage_verified = 0.0

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