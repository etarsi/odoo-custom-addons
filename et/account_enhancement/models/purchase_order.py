# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)
class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

    period_cut_locked = fields.Boolean(string="Período de Corte Bloqueado", default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("period_cut_locked"):
                raise ValidationError(_("No se puede crear una orden de compra con 'Período de Corte Bloqueado' activo."))
        return super().create(vals_list)

    def write(self, vals):
        for purchase in self:
            if vals.get("period_cut_locked") or purchase.period_cut_locked:
                raise ValidationError(_("No se puede modificar una orden de compra con 'Período de Corte Bloqueado' activo."))
        return super().write(vals)

    def unlink(self):
        for purchase in self:
            if purchase.period_cut_locked:
                raise ValidationError(_("No se puede eliminar una orden de compra con 'Período de Corte Bloqueado' activo."))
        return super().unlink()


class PurchaseOrderLineInherit(models.Model):
    _inherit = "purchase.order.line"

    period_cut_locked = fields.Boolean(string="Período de Corte Bloqueado", related='order_id.period_cut_locked', store=True, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("period_cut_locked"):
                raise ValidationError(_("No se puede crear una línea de orden de compra con 'Período de Corte Bloqueado' activo."))
        return super().create(vals_list)

    def write(self, vals):
        for line in self:
            if vals.get("period_cut_locked") or line.period_cut_locked:
                raise ValidationError(_("No se puede modificar una línea de orden de compra con 'Período de Corte Bloqueado' activo."))
        return super().write(vals)

    def unlink(self):
        for line in self:
            if line.period_cut_locked:
                raise ValidationError(_("No se puede eliminar una línea de orden de compra con 'Período de Corte Bloqueado' activo."))  
        return super().unlink()
