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

    blocked_by_order_control = fields.Boolean(
        string='Bloqueado por Control de Pedidos',
        default=False,
        copy=False
    )
    blocked_reason = fields.Text(
        string='Motivo de Bloqueo',
        copy=False
    )

    def action_set_blocked(self, reason=False):
        for order in self:
            if order.state in ('done', 'cancel'):
                continue

            order.write({
                'state': 'blocked',
                'blocked_by_order_control': True,
                'blocked_reason': reason or _('Cliente bloqueado desde Control de Pedidos.'),
            })

    def action_set_draft_from_blocked(self):
        for order in self:
            if order.state != 'blocked':
                continue

            order.write({
                'state': 'draft',
                'blocked_by_order_control': False,
                'blocked_reason': False,
            })

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