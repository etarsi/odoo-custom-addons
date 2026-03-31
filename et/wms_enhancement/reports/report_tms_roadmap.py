# -*- coding: utf-8 -*-
from odoo import api, models


class ReportTmsRoadmap(models.AbstractModel):
    _name = "report.wms_enhancement.report_tms_roadmap_document"
    _description = "Reporte Hoja de Ruta"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["tms.roadmap"].browse(docids)
        data = data or {}

        return {
            "doc_ids": docs.ids,
            "doc_model": "tms.roadmap",
            "docs": docs,
            "in_ruta": data.get("in_ruta"),
        }