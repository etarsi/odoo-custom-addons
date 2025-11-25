from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class ProductTemplateInherit(models.Model):
    _inherit = "product.template"

    display = fields.Integer(string="Cantidades Display", deafult=0, help="Sive para cantidades contenidas en el CAJA/PAQUETE")

    def _extract_m2m_ids(self, value):
        """Convierte taxes_id (comandos M2M o lista de ints) en un set de IDs."""
        ids_set = set()
        if not value:
            return ids_set

        if isinstance(value, (list, tuple)):
            for item in value:
                # Puede ser comando M2M o un int suelto
                if isinstance(item, (list, tuple)) and item:
                    cmd = item[0]
                    if cmd == 6:      # (6, 0, [ids]) -> setear
                        ids_set |= set(item[2] or [])
                    elif cmd == 4:    # (4, id) -> agregar
                        ids_set.add(item[1])
                    elif cmd == 3:    # (3, id) -> quitar
                        ids_set.discard(item[1])
                    elif cmd == 5:    # (5) -> clear
                        ids_set.clear()
                    # cmd == 0 (create) no se puede resolver a id acá
                elif isinstance(item, int):
                    ids_set.add(item)
        return ids_set

    @api.model
    def create(self, vals):
        res = super(ProductTemplateInherit, self).create(vals)
        if res.detailed_type and res.detailed_type == 'product':
            if res.tracking != 'lot':
                raise ValidationError(_("Los productos deben tener seguimiento por Lote, si es almacenable."))
        return res
    
    def write(self, vals):
        res = super(ProductTemplateInherit, self).write(vals)
        for record in self:
            if record.detailed_type and record.detailed_type == 'product':
                if record.tracking != 'lot':
                    raise ValidationError(_("Los productos deben tener seguimiento por Lote, si es almacenable."))
        return res