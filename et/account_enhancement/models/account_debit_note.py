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
        self.ensure_one()
        new_moves = self.env["account.move"]

        for move in self.move_ids.with_context(include_business_fields=True):
            default_values = self._prepare_default_values(move)

            # Crear sin validación intermedia, luego recomputamos y queda balanceado
            new_move = move.with_context(check_move_validity=False).copy(default=default_values)

            # Si el origen es NC y el usuario quiere copiar líneas, recreamos invoice_line_ids POSITIVAS
            # (preservando sale_line_ids) y recomputamos impuestos + cuenta a cobrar/pagar.
            if self.copy_lines and move.move_type in ("out_refund", "in_refund"):
                cmds = self._build_positive_invoice_line_cmds(move)
                new_move.with_context(check_move_validity=False).write({"invoice_line_ids": cmds})

                new_move.with_context(check_move_validity=False)._recompute_dynamic_lines(
                    recompute_all_taxes=True
                )

            new_moves |= new_move

        action = {
            "name": _("Debit Notes"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "context": {"default_move_type": new_moves[:1].move_type if new_moves else "out_invoice"},
        }
        if len(new_moves) == 1:
            action.update({"view_mode": "form", "res_id": new_moves.id})
        else:
            action.update({"view_mode": "list,form", "domain": [("id", "in", new_moves.ids)]})
        return action