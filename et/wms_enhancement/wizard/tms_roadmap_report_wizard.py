# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TmsRoadmapReportWizard(models.TransientModel):
    _name = "tms.roadmap.report.wizard"
    _description = "Reporte de Hoja de Ruta"

    in_ruta = fields.Selection([
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
        ("6", "6")], string="Ind. Vuelta-Ruta", required=True, default="1")
    
    tms_roadmap_id = fields.Many2one("tms.roadmap", string="Hoja de Ruta", required=True)
    
    
    def action_print_report(self):
        self.ensure_one()

        if not self.tms_roadmap_id:
            raise UserError(_("No se ha seleccionado ninguna Hoja de Ruta."))

        return self.env.ref(
            "wms_enhancement.action_report_tms_roadmap"
        ).report_action(
            self.tms_roadmap_id,
            data={
                "in_ruta": self.in_ruta,
            }
        )