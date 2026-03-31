# -*- coding: utf-8 -*-
from odoo import api, models
import logging
_logger = logging.getLogger(__name__)


class ReportTmsRoadmap(models.AbstractModel):
    _name = "report.wms_enhancement.report_tms_roadmap_document"
    _description = "Reporte Hoja de Ruta"

    @api.model
    def _get_report_values(self, docids, data=None):
        if not docids:
            docids = data.get('context', {}).get('active_ids', [])
        tms_roadmap_id = data.get('context', {}).get('active_ids')
        docs = self.env["tms.roadmap"].browse(tms_roadmap_id)
        return {
            "doc_ids": docs.ids,
            "doc_model": "tms.roadmap",
            "docs": docs,
            "in_ruta": data.get("in_ruta"),
        }