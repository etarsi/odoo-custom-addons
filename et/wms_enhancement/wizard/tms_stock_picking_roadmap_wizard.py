# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TmsStockPickingRoadmapWizard(models.TransientModel):
    _name = "tms.stock.picking.roadmap.wizard"
    _description = "Vincular/Crear HDR desde Ruteos"

    type = fields.Selection([
        ("link", "Vincular a HDR existente"),
        ("create", "Crear nueva HDR"),
    ], required=True, default="link")

    stock_picking_ids = fields.Many2many("tms.stock.picking", string="Ruteos", required=True)

    roadmap_id = fields.Many2one("tms.roadmap", string="Hoja de Ruta (existente)")
    transport_id = fields.Many2one("tms.transport", string="Vehículo")
    empresa_id = fields.Many2one("delivery.carrier", string="Empresa")
    industry_ids = fields.Many2many("res.partner.industry", string="Zonas", compute="_compute_industry_ids", store=True, tracking=True)
    assistants = fields.Integer(string="Ayudantes", default=0)

    line_ids = fields.One2many(
        "tms.stock.picking.roadmap.wizard.line",
        "wizard_id",
        string="Líneas a crear",
    )

    total_bulk_defendant = fields.Float(
        string="Total bultos demandados",
        compute="_compute_total_bulk_defendant",
        store=False,
    )
    
    def _compute_industry_ids(self):
        for rec in self:
            industry_ids = rec.stock_picking_ids.mapped('industry_id').ids
            rec.industry_ids = [(6, 0, industry_ids)]

    @api.depends("stock_picking_ids")
    def _compute_total_bulk_defendant(self):
        for rec in self:
            rec.total_bulk_defendant = sum(rec.stock_picking_ids.mapped("cantidad_bultos"))

    @api.onchange("stock_picking_ids", "type", "roadmap_id")
    def _onchange_build_lines(self):
        """Reconstruye el preview cada vez que cambia la selección."""
        if not self.stock_picking_ids:
            self.line_ids = [(5, 0, 0)]
            return

        lines_cmds = [(5, 0, 0)]
        for p in self.stock_picking_ids:
            lines_cmds.append((0, 0, {
                "tms_stock_picking_id": p.id,
                "wms_task_id": p.wms_task_id.id if p.wms_task_id else False,
                "partner_id": p.partner_id.id if p.partner_id else False,
                "direction": getattr(p, "direccion_entrega", False) or getattr(p, "direction", False),
                "bulto_defendant": getattr(p, "bulk_defendant", 0.0) or 0.0,
                "industry_id": p.industry_id.id if p.industry_id else False,
                # si tenés picking de bultos, setearlo acá:
                "bulto_picking": getattr(p, "bulk_picking", 0.0) or 0.0,
            }))
        self.line_ids = lines_cmds

    def action_confirm(self):
        self.ensure_one()
        if not self.stock_picking_ids:
            raise UserError(_("Seleccioná al menos un ruteo."))

        # 1) Determinar HDR
        if self.type == "link":
            if not self.roadmap_id:
                raise UserError(_("Seleccioná una Hoja de Ruta existente."))
            roadmap = self.roadmap_id
        else:
            if not self.transport_id:
                raise UserError(_("Seleccioná un vehículo."))
            # Creamos UNA HDR para todas las líneas (como tu Excel)
            roadmap = self.env["tms.roadmap"].create({
                "transport_id": self.transport_id.id,
                "patente": self.transport_id.patente_trc or self.transport_id.patente_semi,
                "assistants": self.assistants,
                "industry_ids": [(6, 0, self.industry_ids.ids)] if self.industry_ids else False,
            })

        # 2) Crear líneas reales desde el preview (lo que el usuario editó)
        Line = self.env["tms.roadmap.line"]
        for wl in self.line_ids:
            if not wl.tms_stock_picking_id:
                continue
            if wl.wms_task_id:
                # Si la línea del wizard tiene tarea WMS, buscamos si ya existe una línea HDR vinculada a esa tarea
                existing_line = self.env["tms.roadmap.line"].search([
                    ("wms_task_id", "=", wl.wms_task_id.id),
                    ("roadmap_id", "!=", roadmap.id),
                    ("is_canceled", "=", False),
                ], limit=1)
                if existing_line:
                    raise UserError(_("La tarea WMS '%s' ya está vinculada a la línea de Hoja de Ruta '%s'. No se puede vincular el mismo ruteo a dos hojas de ruta.") % (wl.wms_task_id.name, existing_line.roadmap_id.name))
            Line.create({
                "roadmap_id": roadmap.id,
                "tms_stock_picking_id": wl.tms_stock_picking_id.id,
                "wms_task_id": wl.wms_task_id.id if wl.wms_task_id else False,
                "partner_id": wl.partner_id.id if wl.partner_id else False,
                "direction": wl.direction,
                "industry_id": wl.industry_id.id if wl.industry_id else False,
                "in_ruta": wl.in_ruta,
                "type_roadmap": wl.type_roadmap,
                "bulk_defendant": wl.bulto_defendant,
                "bulk_picking": wl.bulto_picking,
            })
        # opcional: abrir la HDR creada/vinculada
        return {
            "type": "ir.actions.act_window",
            "name": _("Hoja de Ruta"),
            "res_model": "tms.roadmap",
            "view_mode": "form",
            "res_id": roadmap.id,
            "target": "current",
        }


class TmsStockPickingRoadmapWizardLine(models.TransientModel):
    _name = "tms.stock.picking.roadmap.wizard.line"
    _description = "Preview líneas HDR (wizard)"
    _order = "id"

    wizard_id = fields.Many2one("tms.stock.picking.roadmap.wizard", required=True, ondelete="cascade")
    tms_stock_picking_id = fields.Many2one("tms.stock.picking", string="Ruteo", required=True)
    wms_task_id = fields.Many2one("wms.task", string="Tarea de picking")
    partner_id = fields.Many2one("res.partner", string="Cliente")
    industry_id = fields.Many2one("res.partner.industry", string="Zona")
    direction = fields.Char(string="Dirección")
    bulto_defendant = fields.Float(string="Bultos Demandados")
    bulto_picking = fields.Float(string="Bultos Pickeados")
    type_roadmap = fields.Selection(string="Tipo", selection=[
        ("delivery", "Entrega"),
        ("pickup", "Retiro"),
    ], required=True, default="delivery", tracking=True)
    in_ruta = fields.Selection(string="Ind. Vuelta-Ruta", selection=[
        ('1', "1"),
        ('2', "2"),
        ('3', "3"),
        ('4', "4"),
        ('5', "5"),
        ('6', "6"),
    ], default='1', store=True, tracking=True)
    
    
    @api.depends("tms_stock_picking_id")
    def _compute_wms_task_id(self):
        for rec in self:
            if rec.tms_stock_picking_id:
                rec.wms_task_id = rec.tms_stock_picking_id.wms_task_id if rec.tms_stock_picking_id.wms_task_id else False
                rec.partner_id = rec.tms_stock_picking_id.partner_id if rec.tms_stock_picking_id.partner_id else False
                rec.direction = getattr(rec.tms_stock_picking_id, "direccion_entrega", False) or getattr(rec.tms_stock_picking_id, "direction", False)
                rec.industry_id = rec.tms_stock_picking_id.industry_id if rec.tms_stock_picking_id.industry_id else False
                rec.bulto_defendant = getattr(rec.tms_stock_picking_id, "cantidad_bultos", 0.0) or 0.0
                rec.bulto_picking = getattr(rec.tms_stock_picking_id, "bulk_picking", 0.0) or 0.0
                
    @api.depends("partner_id")
    def _compute_industry_id(self):
        for rec in self:
            if rec.partner_id:
                rec.industry_id = rec.partner_id.industry_id if rec.partner_id.industry_id else False