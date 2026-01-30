# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TmsCitation(models.Model):
    _name = "tms.citation"
    _description = "Ruteo Citación"
    _order = "date desc, id desc"

    name = fields.Char(string="Referencia", required=True, copy=False, index=True, default=lambda self: _("New"))
    tms_stock_picking_id = fields.Many2one(
        "tms.stock.picking",
        string="Remito Asociado",
        required=False,
        ondelete="restrict",
        index=True,
    )
    date = fields.Datetime(string="Fecha", required=True, default=fields.Datetime.now, index=True)
    mes = fields.Char(string="Mes", compute="_compute_mes", store=True, index=True)
    empresa_id = fields.Many2one("tms.company", string="Empresa", required=True, index=True)
    transport_id = fields.Many2one("delivery.carrier", string="Vehículo", required=True, index=True)
    transport_type_id = fields.Many2one("tms.transport.type", string="Tipo de Vehículo", required=True)
    patente_tractor = fields.Char(string="Patente Tractor")
    patente_semi = fields.Char(string="Patente Semi")
    service_id = fields.Many2one("tms.service", string="Servicio", required=True, index=True)
    area = fields.Selection(string="Área", selection=[
        ("pg", "Pedidos Generales"),
        ("gc", "Grandes Cadenas"),
        ("millan", "Millan"),
        ("other", "Otro"),
    ], required=True, default="pg")
    # Para mostrarlo lindo en UI, después en la vista usás widget="float_time"
    hour_citation = fields.Float(string="Hora Citación", required=True)
    hour_arrival = fields.Float(string="Hora Llegada")
    hiring_id = fields.Many2one("tms.hiring", string="Contratación", required=True)
    observations = fields.Text(string="Observaciones")
    # En la planilla 'Btos G.C' viene con decimales (ej 35.67), por eso Float.
    bulto_count = fields.Float(string="Cantidad de Bultos")

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
            if vals.get("name") in (False, _("New"), "New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("tms.citation") or _("New")
        return super().create(vals_list)