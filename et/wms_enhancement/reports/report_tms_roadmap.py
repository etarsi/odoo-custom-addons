# -*- coding: utf-8 -*-
from odoo import api, models
import logging
_logger = logging.getLogger(__name__)


class ReportTmsRoadmap(models.AbstractModel):
    _name = "report.wms_enhancement.report_tms_roadmap_document"
    _description = "Reporte Hoja de Ruta"

    @api.model
    def _get_report_values(self, docids, data=None):
        _logger.warning("Generando reporte de Hoja de Ruta con docids: %s y data: %s", docids, data)
        if not docids:
            docids = data.get('context', {}).get('active_ids', [])
        _logger.warning("Docids después de verificar: %s", docids)
        tms_roadmap_id = data.get('context', {}).get('active_ids')
        docs = self.env["tms.roadmap"].browse(tms_roadmap_id)
        _logger.warning("Documentos obtenidos: %s", docs)
        _logger.warning("Contexto completo: %s", self.env.context)  # Loguear el contexto completo para depuración
        return {
            "doc_ids": docs.ids,
            "doc_model": "tms.roadmap",
            "docs": docs,
            "in_ruta": data.get("in_ruta"),
        }