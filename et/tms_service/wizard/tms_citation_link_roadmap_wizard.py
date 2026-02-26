from odoo import models, fields

class TmsCitationLinkRoadmapWizard(models.TransientModel):
    _name = "tms.citation.link.roadmap.wizard"
    _description = "Vincular hojas de ruta a una citación"

    citation_id = fields.Many2one("tms.citation", required=True)
    roadmap_ids = fields.Many2many(
        "tms.roadmap",
        string="Hojas de ruta sueltas",
        domain=[("citation_id", "=", False)],
    )

    def action_link(self):
        self.ensure_one()
        if self.roadmap_ids:
            self.roadmap_ids.write({"citation_id": self.citation_id.id})
        return {"type": "ir.actions.act_window_close"}