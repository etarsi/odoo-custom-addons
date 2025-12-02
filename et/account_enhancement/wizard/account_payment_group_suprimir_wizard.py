from odoo import models

class AccountPaymentGroupSuprimirWizard(models.TransientModel):
    _name = 'account.payment.group.suprimir.wizard'
    _description = 'Confirmar supresión de grupos de pago'

    def action_confirm(self):
        """Se ejecuta al pulsar Aceptar en el popup."""
        active_ids = self.env.context.get('active_ids', [])
        records = self.env['account.payment.group'].browse(active_ids)
        records.un_link()
        #cierra el modal y da un mensaje que se elimino correctamente y hay que refrescar la vista en el return
        return {
            'type': 'ir.actions.act_window_close',
            'target': 'new',
            'params': {
                'message': 'Se eliminaron correctamente los grupos de pago. Por favor, refresque la vista.',
                'type': 'success',
            }
        }