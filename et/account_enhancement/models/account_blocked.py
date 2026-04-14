# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime,date,timedelta
from dateutil import relativedelta
from io import StringIO
from odoo.tools.misc import format_date, format_amount
import base64
import csv
import logging
import re
import zipfile
import io
from odoo.tools.float_utils import float_round
import logging
_logger = logging.getLogger(__name__)


class AccountBlocked(models.TransientModel):
    _inherit = 'account.blocked'
    _description = "Contabilidad - Asientos bloqueados por conciliación"

    company_id = models.Many2one('res.company', string="Compañía", required=True, default=lambda self: self.env.company)
    date_limit = models.Date(string="Fecha límite", required=True, default=lambda self: self.env.context.get('fecha_limite', fields.Date.context_today(self)))
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('blocked', 'Bloqueado'),
        ('unblocked', 'Desbloqueado'),
    ], string="Estado", default='draft', readonly=True, copy=False, tracking=True)
    
    #UNO SOLO POR COMPAÑÍA
    _sql_constraints = [
        ('company_id_uniq', 'unique(company_id)', 'Solo puede haber un registro de bloqueo por compañía.'),
    ]



    #---------------------------
    # Acciones de bloqueo
    #---------------------------
    def action_block(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'blocked'
                record.action_lock_period_cut()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Periodo contable bloqueado"),
                    'message': f'Se bloquearon correctamente los periodos contables para la compañía {self.company_id.name}. Por favor, refresque la vista.',
                    "type": "success",
                    "sticky": True
                }
            }
    
    #---------------------------
    # Acciones de desbloqueo
    #---------------------------
    def action_unblock(self):
        for record in self:
            if record.state == 'blocked':
                record.state = 'unblocked'
                record.unlock_contable()
                
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Periodo contable desbloqueado"),
                    'message': f'Se desbloquearon correctamente los periodos contables para la compañía {self.company_id.name}. Por favor, refresque la vista.',
                    "type": "success",
                    "sticky": True
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
            WHERE company_id = %s AND date_order <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_limit))
        # Bloquear en purchase.order
        sql = """
            UPDATE purchase_order SET period_cut_locked = TRUE
            WHERE company_id = %s AND date_order <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_limit))
        # Bloquear en account.payment.group
        sql = """
            UPDATE account_payment_group SET period_cut_locked = TRUE
            WHERE company_id = %s AND payment_date <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_limit))
        # Bloquear en account.move
        sql = """
            UPDATE account_move SET period_cut_locked = TRUE
            WHERE company_id = %s AND date <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_limit))


    def unlock_contable(self):
        """Método para desbloquear el periodo contable, se puede ejecutar desde un botón en la vista de configuración."""
        self.ensure_one()
        # Desbloquear en sale.order
        sql = """
            UPDATE sale_order SET period_cut_locked = FALSE
            WHERE company_id = %s AND date_order <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_limit))
        # Desbloquear en purchase.order
        sql = """
            UPDATE purchase_order SET period_cut_locked = FALSE
            WHERE company_id = %s AND date_order <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_limit))
        # Desbloquear en account.payment.group
        sql = """
            UPDATE account_payment_group SET period_cut_locked = FALSE
            WHERE company_id = %s AND payment_date <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_limit))
        # Desbloquear en account.move
        sql = """
            UPDATE account_move SET period_cut_locked = FALSE
            WHERE company_id = %s AND date <= %s
        """
        self.env.cr.execute(sql, (self.company_id.id, self.date_limit))
        
