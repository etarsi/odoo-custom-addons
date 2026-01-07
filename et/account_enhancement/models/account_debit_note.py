from odoo import models, _
import logging

_logger = logging.getLogger(__name__)


class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'

    def _get_new_moves_from_action(self, action):
        Move = self.env["account.move"]
        if action.get("res_id"):
            return Move.browse(action["res_id"])
        for d in (action.get("domain") or []):
            if isinstance(d, (list, tuple)) and len(d) == 3 and d[0] == "id" and d[1] == "in":
                return Move.browse(d[2])
        return Move.browse()

    def _build_invoice_line_cmds_from_source(self, src_move):
        """Crea comandos para invoice_line_ids en positivo, preservando sale_line_ids."""
        cmds = [(5, 0, 0)]
        for line in src_move.invoice_line_ids.with_context(include_business_fields=True):
            lvals = line.copy_data()[0]

            # Preservar vínculos a pedidos (por seguridad)
            if line.sale_line_ids:
                lvals["sale_line_ids"] = [(6, 0, line.sale_line_ids.ids)]
            if getattr(line, "purchase_line_id", False) and line.purchase_line_id:
                lvals["purchase_line_id"] = line.purchase_line_id.id

            # Secciones / notas: no tocar signos
            if not lvals.get("display_type"):
                if lvals.get("quantity") is not None:
                    lvals["quantity"] = abs(lvals["quantity"])
                if lvals.get("price_unit") is not None:
                    lvals["price_unit"] = abs(lvals["price_unit"])

            # Limpieza defensiva: NO arrastrar campos contables ya calculados
            for k in (
                "move_id",
                "debit", "credit", "balance", "amount_currency",
                "tax_line_id",
                "matched_debit_ids", "matched_credit_ids",
                "full_reconcile_id",
            ):
                lvals.pop(k, None)

            cmds.append((0, 0, lvals))
        return cmds

    def create_debit(self):
        self.ensure_one()
        # Crear sin validar a mitad de proceso (luego queda balanceado al recomputar)
        action = super(AccountDebitNote, self.with_context(check_move_validity=False)).create_debit()
        new_moves = self._get_new_moves_from_action(action)

        if not self.move_ids:
            return action
        src_move = self.move_ids[0].with_context(include_business_fields=True)
        # Solo tu caso objetivo
        if src_move.move_type == "out_refund" and self.copy_lines:
            cmds = self._build_invoice_line_cmds_from_source(src_move)
            for new_move in new_moves.with_context(check_move_validity=False):
                # 1) Borrar TODAS las líneas existentes para evitar mezcla/duplicado
                new_move.write({"line_ids": [(5, 0, 0)]})
                # 2) Agregar líneas comerciales (invoice_line_ids) desde el origen (en positivo)
                new_move.write({"invoice_line_ids": cmds})
                # 3) Recalcular dinámicos: impuestos + cuenta a cobrar/pagar => balancea el asiento
                new_move._recompute_dynamic_lines(recompute_all_taxes=True)
                # 4) Recalcular tipo de documento LATAM y aplicar onchange (como el módulo que viste)
                if hasattr(new_move, "_compute_l10n_latam_document_type"):
                    new_move._compute_l10n_latam_document_type()
                if hasattr(new_move, "_onchange_l10n_latam_document_type_id"):
                    new_move._onchange_l10n_latam_document_type_id()

        return action