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
        return default_values