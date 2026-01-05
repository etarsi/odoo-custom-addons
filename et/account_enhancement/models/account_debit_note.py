from odoo import models, _
import logging
_logger = logging.getLogger(__name__)

class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    
    def _prepare_default_values(self, move):
        vals = super()._prepare_default_values(move)

        # 1) SIEMPRE que el origen sea NC de cliente, arreglar tipo de documento y numeración
        if move.move_type == "out_refund":
            dt = self.env.ref(
                "l10n_ar_debit_note.l10n_latam_document_type_ar_debit_note",
                raise_if_not_found=False
            )
            vals.update({
                # Si existe, fuerzo ND; si no, lo limpio para que lo determine la config
                "l10n_latam_document_type_id": dt.id if dt else False,

                # Limpieza numeración / secuencia (evita copiar datos del comprobante origen)
                "l10n_latam_document_number": False,
                "l10n_latam_manual_document_number": False,
            })

        # 2) Si además estás copiando líneas desde la NC cliente, forzar montos positivos
        if self.copy_lines and move.move_type == "out_refund":
            new_invoice_lines = []
            for line in move.invoice_line_ids:
                lvals = line.copy_data()[0]

                # No tocar líneas sección/nota
                if lvals.get("display_type"):
                    new_invoice_lines.append((0, 0, lvals))
                    continue

                # Limpieza campos contables que no conviene clonar
                for k in (
                    "id", "move_id",
                    "debit", "credit", "balance", "amount_currency",
                    "matched_debit_ids", "matched_credit_ids",
                    "full_reconcile_id",
                ):
                    lvals.pop(k, None)

                # Forzar positivo
                if lvals.get("quantity") is not None:
                    lvals["quantity"] = abs(lvals["quantity"])
                if lvals.get("price_unit") is not None:
                    lvals["price_unit"] = abs(lvals["price_unit"])

                new_invoice_lines.append((0, 0, lvals))

            # Evita copiar apuntes contables ya firmados del crédito
            vals["line_ids"] = [(5, 0, 0)]
            vals["invoice_line_ids"] = new_invoice_lines

        return vals