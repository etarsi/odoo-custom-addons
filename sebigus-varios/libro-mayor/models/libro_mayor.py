# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo import tools

_logger = logging.getLogger(__name__)


class Libro_mayor(models.Model):
    _name = 'libro.mayor'
    _description = 'Libro_mayor'
    _auto = False
    name = fields.Char('name')
    date = fields.Date('date')
    date_maturity = fields.Date('date_maturity')
    matching_number = fields.Char('matching_number')
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
    )
    company_currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    balance = fields.Monetary(
        string='Balance',
        currency_field='company_currency_id',
    )
    amount_residual = fields.Monetary(
        string='Amount Residual',
        currency_field='company_currency_id',
    )
    
    
    def init(self):
        print("Connected")
        tools.drop_view_if_exists(self._cr, 'libro_mayor')
        self._cr.execute("""
                        CREATE OR REPLACE VIEW libro_mayor AS (
                        select   row_number() OVER () as id,
                        company_id,partner_id,date,move_name as name,date_maturity,sum(amount_residual) as amount_residual,sum(balance) as balance,matching_number from account_move_line 
                        where 
                        parent_state = 'posted' and
                        balance != 0 and 
                        account_id in (select id from account_account where internal_type in ('payable','receivable') )
                        group by date,move_name,date_maturity,matching_number,company_id,partner_id );
                        """ )