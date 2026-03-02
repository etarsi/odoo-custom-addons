# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class TmsTransportReassignWizard(models.TransientModel):
    _name = "tms.transport.reassign.wizard"
    _description = "Reasignar vehículos a empresa de transporte"

    carrier_id = fields.Many2one(
        "delivery.carrier",
        string="Empresa de Transporte",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )

    transport_ids = fields.Many2many(
        "tms.transport",
        string="Vehículos a reasignar",
        domain=[("active", "=", True), ("delivery_carrier_id", "=", False)],
    )

    def action_reassign(self):
        self.ensure_one()
        if not self.carrier_id:
            raise UserError(_("No se pudo determinar la empresa (carrier)."))

        if not self.transport_ids:
            return {"type": "ir.actions.act_window_close"}

        # Reasigna (mueve) los vehículos a esta empresa
        self.transport_ids.write({"delivery_carrier_id": self.carrier_id.id})

        return {"type": "ir.actions.act_window_close"}