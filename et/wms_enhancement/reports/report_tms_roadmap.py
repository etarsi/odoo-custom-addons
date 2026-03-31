# -*- coding: utf-8 -*-
from odoo import api, models
import logging
_logger = logging.getLogger(__name__)


class ReportTmsRoadmap(models.AbstractModel):
    _name = "report.wms_enhancement.report_tms_roadmap_document"
    _description = "Reporte Hoja de Ruta"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["tms.roadmap"].browse(docids)
        data = data or {}
        _logger.warning(f"Data recibida en el reporte: {data}")
        _logger.warning(f"Documentos recibidos en el reporte: {docs.ids}")
        _logger.warning(f"Contexto del reporte: {self.env.context}")
        return {
            "doc_ids": docs.ids,
            "doc_model": "tms.roadmap",
            "docs": docs,
            "in_ruta": data.get("in_ruta"),
        }