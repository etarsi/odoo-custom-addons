from odoo import models, fields, api, _
from odoo.http import request, content_disposition
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError, AccessError
import logging
import math
import requests
from itertools import groupby
from datetime import timedelta, date

_logger = logging.getLogger(__name__)


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    order_control_state = fields.Selection([
        ('unreviewed', 'Sin Revisar'),
        ('approved', 'Autorizado'),
        ('blocked', 'Bloqueado'),
        ], string='Estado', default='unreviewed', tracking=True)

    last_review_date = fields.Datetime(string="Última Revisión", readonly=True)
    last_review_user_id = fields.Many2one('res.users', string="Revisado por", readonly=True)

    block_reason = fields.Text(string="Motivo de Bloqueo")
    risk_note = fields.Text(string="Observación del Gerente")



    last_purchase_date = fields.Date(string="Última Compra", compute="_compute_sales_data", store=True)
    last_purchase_amount = fields.Monetary(string="Monto Última Compra", compute="_compute_sales_data", store=True)
    days_without_purchase = fields.Integer(string="Días sin Comprar", compute="_compute_days_without_purchase", store=True)

    season_purchase_count = fields.Integer(string="Compras Temporada", compute="_compute_sales_data", store=True)
    draft_sale_order_count = fields.Integer(string="Pedidos Borrador", compute="_compute_draft_orders")



    total_debt = fields.Monetary(string="Deuda Total", compute="_compute_debt", store=True)
    overdue_debt = fields.Monetary(string="Deuda Vencida", compute="_compute_debt", store=True)
    max_overdue_days = fields.Integer(string="Días de Mora", compute="_compute_debt", store=True)



    is_new_customer = fields.Boolean(string="Cliente Nuevo", compute="_compute_alerts", store=True)
    reactivated_customer_alert = fields.Boolean(string="Cliente Reactivado", compute="_compute_alerts", store=True)
    sudden_purchase_alert = fields.Boolean(string="Compra Inusual", compute="_compute_alerts", store=True)
    new_customer_high_risk_alert = fields.Boolean(string="Nuevo Cliente - Compra Alta", compute="_compute_alerts", store=True)

    credit_alert_summary = fields.Text(string="Resumen de Alertas", compute="_compute_alerts", store=True)

    # =========================
    # COMPUTES
    # =========================

    def _compute_sales_data(self):
        for partner in self:
            orders = self.env['sale.order'].search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['sale', 'done'])
            ], order='date_order desc')

            if orders:
                last_order = orders[0]
                partner.last_purchase_date = last_order.date_order.date()
                partner.last_purchase_amount = last_order.amount_total
                partner.season_purchase_count = len(orders)
            else:
                partner.last_purchase_date = False
                partner.last_purchase_amount = 0
                partner.season_purchase_count = 0

    def _compute_days_without_purchase(self):
        today = date.today()
        for partner in self:
            if partner.last_purchase_date:
                partner.days_without_purchase = (today - partner.last_purchase_date).days
            else:
                partner.days_without_purchase = 9999

    def _compute_draft_orders(self):
        for partner in self:
            count = self.env['sale.order'].search_count([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['draft', 'sent'])
            ])
            partner.draft_sale_order_count = count

    def _compute_debt(self):
        today = fields.Date.today()

        for partner in self:
            moves = self.env['account.move'].search([
                ('partner_id', '=', partner.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
            ])

            total = 0
            overdue = 0
            max_days = 0

            for move in moves:
                residual = move.amount_residual
                total += residual

                if move.invoice_date_due and move.invoice_date_due < today:
                    overdue += residual
                    days = (today - move.invoice_date_due).days
                    if days > max_days:
                        max_days = days

            partner.total_debt = total
            partner.overdue_debt = overdue
            partner.max_overdue_days = max_days

    def _compute_alerts(self):
        for partner in self:

            # Cliente nuevo
            partner.is_new_customer = partner.season_purchase_count < 3

            # Reactivado
            partner.reactivated_customer_alert = partner.days_without_purchase > 120 and partner.last_purchase_date

            # Compra inusual (simple)
            partner.sudden_purchase_alert = partner.last_purchase_amount > 0 and partner.last_purchase_amount > 30000000

            # Nuevo cliente con compra alta
            partner.new_customer_high_risk_alert = partner.is_new_customer and partner.last_purchase_amount > 50000000

            # Resumen
            alerts = []
            if partner.is_new_customer:
                alerts.append("Cliente nuevo")
            if partner.reactivated_customer_alert:
                alerts.append("Cliente reactivado")
            if partner.sudden_purchase_alert:
                alerts.append("Compra inusual")
            if partner.new_customer_high_risk_alert:
                alerts.append("Nuevo cliente con compra alta")

            partner.credit_alert_summary = ", ".join(alerts) if alerts else "Sin alertas"

    # =========================
    # ACCIONES
    # =========================





    def action_set_approved(self):
        for rec in self:
            rec.write({
                'order_control_state': 'approved',
                'last_review_date': fields.Datetime.now(),
                'last_review_user_id': self.env.user.id,
            })

    def action_set_blocked(self):
        SaleOrder = self.env['sale.order']

        for rec in self:
            rec.write({
                'order_control_state': 'blocked',
                'last_review_date': fields.Datetime.now(),
                'last_review_user_id': self.env.user.id,
            })

            orders_to_block = SaleOrder.search([
                ('partner_id', '=', rec.id),
                ('state', 'in', ['draft', 'sent']),
            ])

            orders_to_block.action_set_blocked(
                reason=rec.block_reason or _('Cliente bloqueado desde la ficha de Control de Pedidos.')
            )

    def action_set_unreviewed(self):
        for rec in self:
            rec.write({
                'order_control_state': 'unreviewed',
                'last_review_date': fields.Datetime.now(),
                'last_review_user_id': self.env.user.id,
            })