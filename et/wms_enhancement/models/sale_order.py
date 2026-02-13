from odoo import _, models, fields, api


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
    
    
    def action_confirm(self):
        res = super().action_confirm()
        for record in self:          

            ### TRANSFER CREATION
            if record.transfer_id:
                continue

            transfer_vals = {
                'operation_type':'outgoing',
                'partner_id':record.partner_id.id,
                'partner_address_id':record.partner_shipping_id.id or False,
                'sale_type':record.condicion_m2m.name,
                'sale_id':record.id,
                'state': 'pending',
            }

            transfer_id = self.env['wms.transfer'].create(transfer_vals)
            transfer_lines_list = []
            for line in record.order_line:
               if line.product_id:
                   transfer_line = {
                       'transfer_id': transfer_id.id,
                       'product_id': line.product_id.id,
                       'state': 'pending',
                       'invoice_state': 'no',
                       'sale_line_id': line.id,
                       'uxb': line.product_packaging_id.qty or False,
                       'qty_demand': line.product_uom_qty or 0,
                   }

                   transfer_lines_list.append(transfer_line)
            
            self.env['wms.transfer.line'].create(transfer_lines_list)

            record.transfer_id = transfer_id.id
            


class SaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'
    
    wms_qty_delivered = fields.Float(string="Cantidad Entregada")
    wms_qty_invoiced = fields.Float(string="Cantidad Facturada")