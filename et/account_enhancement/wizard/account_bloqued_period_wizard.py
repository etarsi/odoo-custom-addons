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
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)


    def action_confirm(self):
        """Se ejecuta al pulsar Aceptar en el popup."""
        self.ensure_one()
        self.action_lock_period_cut()
        #cierra el modal y da un mensaje que se elimino correctamente y hay que refrescar la vista en el return
        return {
            'type': 'ir.actions.act_window_close',
            'target': 'new',
            'params': {
                'message': 'Se bloquearon correctamente los periodos contables. Por favor, refresque la vista.',
                'type': 'success',
            }
        }
        
    # ---------------------------
    # Validaciones de bloqueo de Periodo en modelos relacionados
    # ---------------------------
    def action_lock_period_cut(self):
        self.ensure_one()
        #bloquear periodo anteriores a date_start en modelos relacionados (sale.order, purchase.order, account.payment)
        # Bloquear en sale.order
        sql = """
            UPDATE sale_order SET period_cut_locked = TRUE
            WHERE company_id = %s AND date_order >= %s AND date_order <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_start, self.date_end))
        # Bloquear en purchase.order
        sql = """
            UPDATE purchase_order SET period_cut_locked = TRUE
            WHERE company_id = %s AND date_order >= %s AND date_order <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_start, self.date_end))
        # Bloquear en account.payment.group
        sql = """
            UPDATE account_payment_group SET period_cut_locked = TRUE
            WHERE company_id = %s AND payment_date >= %s AND payment_date <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_start, self.date_end))
        # Bloquear en account.move
        sql = """
            UPDATE account_move SET period_cut_locked = TRUE
            WHERE company_id = %s AND date >= %s AND date <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_start, self.date_end))