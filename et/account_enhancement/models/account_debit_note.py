from odoo import models, _
import logging
_logger = logging.getLogger(__name__)

class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    
    def _prepare_default_values(self, move):
        default_values = super()._prepare_default_values(move)
        #que migre las lineas de producto y no solo las de impuestos si es nota de credito de cliente
        if move.move_type == 'out_refund' and self.copy_lines:
            line_ids = []
            for line in move.line_ids:
                line_data = line.copy_data({
                    'move_id': False,
                    'tax_line_id': False,
                    'debit': 0.0,
                    'credit': 0.0,
                })[0]
                line_ids.append((0, 0, line_data))
            default_values['line_ids'] = line_ids
            _logger.info("Copied product lines for debit note from move %s", move.name)
            _logger.info("Default values: %s", default_values)
        return default_values
    
    def create_debit(self):
        res = super().create_debit()

        Move = self.env["account.move"]
        new_moves = Move.browse()

        # Caso 1: se creó 1
        if res.get("res_id"):
            new_moves = Move.browse(res["res_id"])

        # Caso 2: se crearon varios -> viene domain [('id','in',[...])]
        else:
            for d in (res.get("domain") or []):
                if isinstance(d, (list, tuple)) and len(d) == 3 and d[0] == "id" and d[1] == "in":
                    new_moves = Move.browse(d[2])
                    break
        _logger.info("New debit note moves created: %s", new_moves.mapped("name"))
        _logger.info("Recomputing latam document types for debit notes")
        # Recomputar tipo de doc + onchange para todos
        for m in new_moves:
            m._compute_l10n_latam_document_type()
            m._onchange_l10n_latam_document_type_id()

        return res