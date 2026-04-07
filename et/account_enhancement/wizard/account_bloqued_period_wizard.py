# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_is_zero
import logging
_logger = logging.getLogger(__name__)

class AccountBloquedPeriodWizard(models.TransientModel):
    _name = 'account.bloqued.period.wizard'
    _description = 'Bloquear periodo contable'
    
    date_start = fields.Date(string="Fecha Inicio", required=True, default=lambda self: fields.Date.to_string(fields.Date.today().replace(month=1, day=1)), index=True)
    date_end = fields.Date(string="Fecha Fin", required=True, default=lambda self: fields.Date.to_string(fields.Date.today().replace(month=12, day=31)), index=True)

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