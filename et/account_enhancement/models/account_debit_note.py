from odoo import models, _
import logging
_logger = logging.getLogger(__name__)

class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    
    def create_debit(self):
        """ Properly compute the latam document type of type debit note. """
        res = super().create_debit()
        _logger.info("AccountDebitNote.create_debit called, result: %s", res)0
        new_move_id = res.get('res_id')
        if self.move_ids[0].move_type == 'out_refund':
            _logger.info("Creating debit note for customer refund.")
            if new_move_id:
                new_move = self.env['account.move'].browse(new_move_id)
                # Agregar lines de invoice original a la nota de débito
                for line in self.move_ids[0].invoice_line_ids:
                    new_move.invoice_line_ids += line.copy({
                        'move_id': new_move.id,
                    })                
                _logger.info("Added invoice lines to debit note: %s", new_move.invoice_line_ids)
            _logger.info("Debit note created with ID: %s", new_move_id)
        return res