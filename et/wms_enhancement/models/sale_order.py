from odoo import models, fields, api


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'


    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")

    def action_open_wms_transfer(self):
       self.ensure_one()
       if not self.transfer_id:
           return False

       return {
           'type': 'ir.actions.act_window',
           'name': _('Transferencia WMS'),
           'res_model': 'wms.transfer',
           'view_mode': 'form',
           'res_id': self.transfer_id.id,
           'target': 'current',
       }