from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class StockPickingInherit(models.Model):
    _inherit = "stock.picking"

    def write(self, vals):
        # Solo bloquear si NO viene el contexto especial
        if (
            vals.get('picking_type_id')
            and not self.env.context.get('force_modify_picking')
            and any(picking.state in ('done', 'cancel') for picking in self)
        ):
            raise ValidationError(_("Cambiar el tipo de operación de este registro está prohibido en este momento."))
        return super().write(vals)