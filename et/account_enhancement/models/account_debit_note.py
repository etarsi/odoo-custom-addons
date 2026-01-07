from odoo import models, _
import logging

_logger = logging.getLogger(__name__)


class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'

    def create_debit(self):
        """Recalcula el tipo de documento LATAM y (si aplica) copia líneas desde una NC de cliente."""
        res = super().create_debit()
        _logger.info("AccountDebitNote.create_debit ejecutado. Resultado de la acción: %s", res)

        new_move_id = res.get('res_id')

        # Validaciones defensivas
        if not self.move_ids:
            _logger.warning("No hay comprobantes seleccionados (move_ids vacío). No se realizan ajustes.")
            return res

        move_origen = self.move_ids[0]

        # Solo aplica si el origen es una Nota de Crédito de Cliente y el usuario marcó 'Copiar líneas'
        if move_origen.move_type == 'out_refund' and self.copy_lines:
            _logger.info("Se detectó Nota de Crédito de Cliente (out_refund) con 'Copiar líneas' activado.")

            if not new_move_id:
                _logger.warning(
                    "No se encontró 'res_id' en la acción (posible creación múltiple). "
                    "No se pudieron aplicar ajustes posteriores por ID."
                )
                return res

            new_move = self.env['account.move'].browse(new_move_id)
            _logger.info("Nota de débito creada con ID: %s", new_move_id)

            # Agregar líneas de la factura/NC original a la nota de débito
            _logger.info("Copiando %s líneas del comprobante origen a la nota de débito...", len(move_origen.invoice_line_ids))
            for line in move_origen.invoice_line_ids:
                new_move.invoice_line_ids += line.copy({
                    'move_id': new_move.id,
                })

            _logger.info(
                "Líneas agregadas a la nota de débito. Cantidad total de líneas ahora: %s",
                len(new_move.invoice_line_ids)
            )

            # Recalcular tipo de documento LATAM y disparar onchange
            _logger.info("Recalculando tipo de documento LATAM para la nota de débito ID: %s", new_move_id)
            new_move._compute_l10n_latam_document_type()

            _logger.info("Ejecutando onchange de tipo de documento LATAM para la nota de débito ID: %s", new_move_id)
            new_move._onchange_l10n_latam_document_type_id()

            _logger.info("Proceso finalizado correctamente para la nota de débito ID: %s", new_move_id)

        else:
            _logger.info(
                "No se aplican ajustes: move_type origen=%s, copy_lines=%s",
                move_origen.move_type, self.copy_lines
            )

        return res
