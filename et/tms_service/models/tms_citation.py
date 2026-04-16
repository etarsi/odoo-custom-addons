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
    tms_roadmap_citation_ids = fields.Many2many('tms.roadmap', string='Hojas de Ruta', compute="_compute_tms_roadmap_count", store=False)
    tms_roadmap_citation_count = fields.Integer(string="Cantidad de Hojas de Ruta", compute="_compute_tms_roadmap_count", store=True, tracking=True)
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today, index=True, tracking=True)
    mes = fields.Char(string="Mes", compute="_compute_mes", store=True, index=True, tracking=True)
    empresa_id = fields.Many2one("delivery.carrier", string="Empresa", domain="[('active', '=', True)]", required=True, index=True, tracking=True)
    transport_id = fields.Many2one("tms.transport", string="Vehículo", required=True, index=True, tracking=True)
    transport_type_id = fields.Many2one("tms.transport.type", string="Tipo de Vehículo", tracking=True)
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
    hour_citation = fields.Float(string="Hora Citación", required=True, default=7, tracking=True)
    hour_arrival = fields.Float(string="Hora Llegada", default=14, tracking=True)
    hiring_id = fields.Many2one("tms.hiring", string="Contratación", tracking=True)
    observations = fields.Text(string="Observaciones", tracking=True)
    # En la planilla 'Btos G.C' viene con decimales (ej 35.67), por eso Float.
    total_bulk = fields.Float(string="T. Cantidad de Bultos", compute="_compute_total_bulk", tracking=True)
    total_bulk_verified = fields.Float(string="T. Cantidad de Bultos Pickeados", compute="_compute_total_bulk", store=True, tracking=True)
    percentage_verified = fields.Float(string="Porcentaje Verificado", compute="_compute_percentage_verified", store=True, tracking=True)
    amount_service = fields.Float(string="Importe del Servicio", tracking=True)    
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("pending", "Pendiente"),
            ("completed", "Despachado"),
            ("canceled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    # amount_stock_valued = fields.Float(string="Valoración de Stock Facturado", compute="_compute_amount_stock_valued", tracking=True)
    # def _compute_amount_stock_valued(self):
    #     for rec in self:
    #         amount = 0.0
    #         for roadmap in rec.tms_roadmap_ids:
    #             for line in roadmap.tms_roadmap_line_ids:
    #                 if line.stock_move_id and line.stock_move_id.product_id and line.stock_move_id.product_id.type == "product":
    #                     amount += line.stock_move_id.product_uom_qty * line.stock_move_id.product_id.standard_price
    #         rec.amount_stock_valued = amount

    def _compute_tms_roadmap_count(self):
        for rec in self:
            rec.tms_roadmap_citation_ids = rec.tms_roadmap_ids
            rec.tms_roadmap_citation_count = len(rec.tms_roadmap_citation_ids)
        
    def action_view_tms_roadmaps(self):
        self.ensure_one()
        return {
            "name": _("Hojas de Ruta"),
            "type": "ir.actions.act_window",
            "res_model": "tms.roadmap",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.tms_roadmap_ids.ids)],
            "context": {"default_citation_id": self.id},
        }

    @api.depends("tms_roadmap_ids.total_bulk_defendant", "tms_roadmap_ids.total_bulk_picking")
    def _compute_total_bulk(self):
        for rec in self:
            rec.total_bulk = 0
            rec.total_bulk_verified = 0
            for roadmap in rec.tms_roadmap_ids:
                rec.total_bulk += roadmap.total_bulk_defendant
                rec.total_bulk_verified += roadmap.total_bulk_picking

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
            if rec.state == "canceled":
                raise ValidationError(_("No se pueden publicar hojas de ruta canceladas."))
            rec.state = "pending"
            rec.message_post(body=_("La hoja de ruta ha sido publicada."))
            rec.tms_roadmap_ids.write({"state": "pending"})
            
    def action_draft(self):
        for rec in self:
            if rec.state == "canceled":
                raise ValidationError(_("No se pueden poner en borrador hojas de ruta canceladas."))
            rec.state = "draft"
            rec.message_post(body=_("La hoja de ruta ha sido puesta en borrador."))
            rec.tms_roadmap_ids.write({"state": "draft"})

    def action_cancel(self):
        for rec in self:
            if rec.state == "canceled":
                raise ValidationError(_("La hoja de ruta ya está cancelada."))
            rec.state = "canceled"
            rec.message_post(body=_("La hoja de ruta ha sido cancelada."))
            rec.tms_roadmap_ids.write({"state": "canceled"})
            
    def action_completed(self):
        for rec in self:
            if rec.state == "completed":
                raise ValidationError(_("No se pueden completar hojas de ruta ya completadas."))
            elif rec.state == "canceled":
                raise ValidationError(_("No se pueden completar hojas de ruta canceladas."))
            rec.state = "completed"
            rec.message_post(body=_("La hoja de ruta ha sido completada."))
            rec.tms_roadmap_ids.write({"state": "completed"})