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

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(
        selection_add=[('blocked', 'Bloqueado')],
        ondelete={'blocked': 'set default'}
    )

    approval_state = fields.Selection(string="Estado de Aprobación", selection=[
        ('pending', 'Sin Revisar'),
        ('blocked','Bloqueado'),
        ('rejected', 'Rechazado')
        ('approved', 'OK')], default='pending')

    blocked_by_order_control = fields.Boolean(
        string='Bloqueado por Control de Pedidos',
        default=False,
        copy=False
    )
    blocked_reason = fields.Text(
        string='Motivo de Bloqueo',
        copy=False
    )

    executive_id = fields.Many2one(
        related='partner_id.executive_id',
        string='Ejecutivo',
        store=False,
        readonly=True
    )

    partner_overdue_debt = fields.Monetary(
        related='partner_id.overdue_debt',
        string='Deuda Total Vencida',
        currency_field='currency_id',
        store=False,
        readonly=True
    )

    def action_set_pending(self):
        for rec in self:
            rec.approval_state = 'pending'

    def action_set_approved(self):
        for rec in self:
            rec.approval_state = 'approved'

    def action_set_rejected(self):
        for rec in self:
            rec.approval_state = 'rejected'
            rec.state = 'rejected'


    def action_confirm(self):
        for order in self:
            if order.state == 'blocked':
                raise UserError(_('No se puede confirmar un pedido bloqueado.'))

            if order.partner_id.order_control_state == 'blocked':
                raise UserError(_('No se puede confirmar un pedido porque el cliente está bloqueado.'))

        return super().action_confirm()
    

    def action_draft(self):
        for order in self:
            if order.state == 'blocked':
                raise UserError(_('No se puede pasar a borrador un pedido bloqueado desde esta acción.'))
        return super().action_draft()
    
    @api.model
    def create(self, vals):
        order = super().create(vals)

        if order.partner_id.order_control_state == 'blocked' and order.state in ('draft', 'sent'):
            order.action_set_blocked(
                reason=_('Pedido bloqueado automáticamente porque el cliente está bloqueado.')
            )

        return order
    

    def write(self, vals):
        if 'partner_id' in vals and vals.get('partner_id'):
            new_partner = self.env['res.partner'].browse(vals['partner_id'])

            for order in self:
                if order.state in ('sale', 'done', 'cancel') and new_partner.order_control_state == 'blocked':
                    raise UserError(
                        _('No se puede asignar un cliente bloqueado a un pedido ya confirmado/finalizado.')
                    )

        res = super().write(vals)

        if 'partner_id' in vals and vals.get('partner_id'):
            new_partner = self.env['res.partner'].browse(vals['partner_id'])

            for order in self:
                if order.state in ('draft', 'sent') and new_partner.order_control_state == 'blocked':
                    order.action_set_blocked(
                        reason=_('Pedido bloqueado automáticamente porque el cliente asignado está bloqueado.')
                    )

        return res
    
    @api.onchange('partner_id')
    def _onchange_partner_id_order_control(self):
        if self.partner_id and self.partner_id.order_control_state == 'blocked':
            warning = {
                'title': _('Cliente bloqueado'),
                'message': _('Este cliente está bloqueado desde Control de Pedidos. Si guardás, el pedido quedará bloqueado.'),
            }
            return {'warning': warning}


    def action_open_order_control_partner(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cliente',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'views': [(self.env.ref('sale_credit_control.view_partner_form_order_control').id, 'form')],
            'res_id': self.partner_id.id,
            'target': 'current',
        }
    
    