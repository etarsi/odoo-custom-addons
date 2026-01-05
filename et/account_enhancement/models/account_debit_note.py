from odoo import models, _
import logging
_logger = logging.getLogger(__name__)

class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    
    def _prepare_default_values(self, move):
        vals = super()._prepare_default_values(move)

        # Siempre corregir doc type si viene de NC cliente
        if move.move_type == "out_refund":
            dt = self.env.ref(
                "l10n_ar_debit_note.l10n_latam_document_type_ar_debit_note",
                raise_if_not_found=False
            )
            vals.update({
                "l10n_latam_document_type_id": dt.id if dt else False,
                "l10n_latam_document_number": False,
                "l10n_latam_manual_document_number": False,
            })

        # Si copio líneas desde NC cliente, recreo líneas en positivo PERO manteniendo links de pedido/compra
        if self.copy_lines and move.move_type == "out_refund":
            new_invoice_lines = []

            for line in move.invoice_line_ids:
                # CLAVE: usar el mismo contexto de negocio
                lvals = line.with_context(include_business_fields=True).copy_data()[0]

                # Mantener explícitamente líneas de pedido/compra (por si copy_data no las trae)
                if "sale_line_ids" not in lvals and line.sale_line_ids:
                    lvals["sale_line_ids"] = [(6, 0, line.sale_line_ids.ids)]
                if "purchase_line_id" not in lvals and line.purchase_line_id:
                    lvals["purchase_line_id"] = line.purchase_line_id.id

                # Si es sección/nota, no tocar signos
                if lvals.get("display_type"):
                    new_invoice_lines.append((0, 0, lvals))
                    continue

                # Limpieza campos contables “firmados”
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

            # Evitar copiar apuntes contables del crédito
            vals["line_ids"] = [(5, 0, 0)]
            vals["invoice_line_ids"] = new_invoice_lines

        return vals