from odoo import models, _
import logging
_logger = logging.getLogger(__name__)

class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    
    def _prepare_default_values(self, move):
        vals = super()._prepare_default_values(move)
        # Solo si estoy copiando líneas y el origen es Nota de Crédito de Cliente
        if self.copy_lines and move.move_type == "out_refund":
            new_invoice_lines = []

            for line in move.invoice_line_ids:
                lvals = line.copy_data()[0]

                # Limpieza de campos que NO conviene clonar tal cual
                # (reconciliaciones / importes contables ya calculados)
                for k in (
                    "id", "move_id",
                    "debit", "credit", "balance", "amount_currency",
                    "matched_debit_ids", "matched_credit_ids",
                    "full_reconcile_id",
                ):
                    lvals.pop(k, None)

                # Forzar positivo (por si el crédito quedó con qty o price negativos)
                if lvals.get("quantity") is not None:
                    lvals["quantity"] = abs(lvals["quantity"])
                if lvals.get("price_unit") is not None:
                    lvals["price_unit"] = abs(lvals["price_unit"])

                new_invoice_lines.append((0, 0, lvals))

            # IMPORTANTÍSIMO:
            # Evita que se copien los line_ids (apuntes) del crédito con su signo.
            vals["line_ids"] = [(5, 0, 0)]
            # Y en su lugar, creamos líneas de factura “limpias” y positivas.
            vals["invoice_line_ids"] = new_invoice_lines
        return vals