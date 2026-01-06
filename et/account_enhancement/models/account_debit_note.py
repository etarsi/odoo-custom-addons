from odoo import models, _
import logging
_logger = logging.getLogger(__name__)

class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    
    def _ar_map_debit_doc_type(self, move):
        """
        Intenta mapear automáticamente el tipo de documento AR:
        NC (3/8/13) -> ND (2/7/12).
        Si no puede, cae al xml_id genérico.
        """
        dt_src = move.l10n_latam_document_type_id
        code = getattr(dt_src, "l10n_ar_afip_code", False)

        map_code = {
            "3": "2",    # NC A -> ND A
            "8": "7",    # NC B -> ND B
            "13": "12",  # NC C -> ND C
        }
        target_code = map_code.get(str(code)) if code else None
        if target_code:
            dt = self.env["l10n_latam.document.type"].search(
                [("country_id.code", "=", "AR"), ("l10n_ar_afip_code", "=", target_code)],
                limit=1
            )
            if dt:
                return dt

        # Fallback genérico (si existe en tu módulo)
        return self.env.ref(
            "l10n_ar_debit_note.l10n_latam_document_type_ar_debit_note",
            raise_if_not_found=False
        )

    def _prepare_default_values(self, move):
        # Respeto tu lógica original de move_type
        if move.move_type in ("in_refund", "out_refund"):
            move_type = "in_invoice" if move.move_type == "in_refund" else "out_invoice"
        else:
            move_type = move.move_type

        vals = {
            "ref": ("%s, %s" % (move.name, self.reason)) if self.reason else move.name,
            "date": self.date or move.date,
            "invoice_date": move.is_invoice(include_receipts=True) and (self.date or move.date) or False,
            "journal_id": (self.journal_id.id if self.journal_id else move.journal_id.id),
            "invoice_payment_term_id": None,
            "debit_origin_id": move.id,
            "move_type": move_type,
        }

        # Importante:
        # - Si copy_lines = False, vaciamos líneas (comportamiento estándar)
        # - Si viene de refund y copy_lines = True, NO vaciamos line_ids (si no, perdés sale_line_ids)
        vals["line_ids"] = [(5, 0, 0)]

        # Si el origen es una NC (cliente o proveedor), corregimos tipo doc y numeración
        if move.move_type in ("out_refund", "in_refund"):
            dt = self._ar_map_debit_doc_type(move)
            vals.update({
                "l10n_latam_document_type_id": dt.id if dt else False,
                "l10n_latam_document_number": False,
                "l10n_latam_manual_document_number": False,
            })

        return vals

    def create_debit(self):
        self.ensure_one()
        new_moves = self.env["account.move"]

        for move in self.move_ids.with_context(include_business_fields=True):
            default_values = self._prepare_default_values(move)
            new_move = move.copy(default=default_values)

            # Si el origen es NC, forzamos líneas "positivas" SIN reconstruirlas,
            # para mantener sale_line_ids / purchase_line_id.
            if self.copy_lines and move.move_type == "out_refund":
                for line in new_move.invoice_line_ids.filtered(lambda l: not l.display_type):
                    if line.quantity < 0:
                        line.quantity = abs(line.quantity)
                    if line.price_unit < 0:
                        line.price_unit = abs(line.price_unit)
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