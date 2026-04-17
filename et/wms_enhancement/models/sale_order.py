from odoo import _, models, fields, api


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'


    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")
    preselection_id = fields.Many2one(string="Preselección", comodel_name="wms.preselection")
    is_fraction = fields.Boolean(string="Es Fraccionado?", default=False, compute="_compute_is_fraction")

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
                'company_id': record.company_id.id,
            }

            transfer_id = self.env['wms.transfer'].create(transfer_vals)
            transfer_lines_list = []
            for line in record.order_line:
               qty_demand = line.product_uom_qty
               if not line.is_available:
                   qty_demand = 0
                   
               if line.product_id:
                   transfer_line = {
                       'transfer_id': transfer_id.id,
                       'product_id': line.product_id.id,
                       'state': 'pending',
                       'invoice_state': 'no',
                       'sale_line_id': line.id,
                       'uxb': line.product_packaging_id.qty or False,
                       'qty_demand': qty_demand,
                    }

                   transfer_lines_list.append(transfer_line)
            
            self.env['wms.transfer.line'].create(transfer_lines_list)
            record.transfer_id = transfer_id.id

    @api.depends('partner_id')
    def _compute_is_fraction(self):
        for record in self:
            tags = record.partner_id.category_id.mapped('name')
            record.is_fraction = 'Fraccionado' in tags

    def cancel_order(self):
        """
            Override del método de cancelación de pedido para cancelar la transferencia asociada.
                - Si el pedido tiene entregas asociadas, no se podrá cancelar.
        """
        for record in self:
            if record.transfer_id and record.transfer_id.state != 'no':
                record.transfer_id.action_cancel()
        res = super().cancel_order()                
        return res
                
    def write(self, vals):
        res = super().write(vals)
        company_id = False
        condicion_m2m = False
        partner_shipping_id = False
        if 'company_id' in vals:
            company_id = True
        if 'condicion_m2m' in vals:
            condicion_m2m = True
        if 'partner_shipping_id' in vals:
            partner_shipping_id = True
        if company_id or condicion_m2m or partner_shipping_id:
            self._actualizar_wms_transfer_task(company_id=company_id, condicion_m2m=condicion_m2m, partner_shipping_id=partner_shipping_id)
        return res
    
    def _actualizar_wms_transfer_task(self, company_id=False, condicion_m2m=False, partner_shipping_id=False):
        for record in self:
            vals_to_write_transfer = {}
            vals_to_write_task = {}
            if company_id:
                vals_to_write_transfer['company_id'] = record.company_id.id
                vals_to_write_task['company_id'] = record.company_id.id
            if condicion_m2m:
                vals_to_write_transfer['sale_type'] = record.condicion_m2m.name
                vals_to_write_task['invoicing_type'] = record.condicion_m2m.name
            if partner_shipping_id:
                vals_to_write_transfer['partner_address_id'] = record.partner_shipping_id.id
                vals_to_write_task['partner_address_id'] = record.partner_shipping_id.id
            #Actualizar company_id en wms.task
            transfers = self.env['wms.transfer'].search([('sale_id', '=', record.id)])
            if transfers:
                transfers.write(vals_to_write_transfer)
                transfers.mapped('task_ids').write(vals_to_write_task)
                
                
class SaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'
    
    wms_qty_delivered = fields.Float(string="Cantidad Entregada")
    wms_qty_invoiced = fields.Float(string="Cantidad Facturada")


    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        return
    
    def write(self, vals):
        res = super().write(vals)
        if 'product_uom_qty' in vals or 'product_packaging_qty' in vals:
            #actualizar cantidad demandada en wms.transfer.line
            for line in self:
                line.update_wms_transfer_line()
        return res
    
    def update_wms_transfer_line(self):
        for line in self:
            transfer_lines = self.env['wms.transfer.line'].search([('sale_line_id', '=', line.id)])
            if transfer_lines:
                transfer_lines.write({
                    'qty_demand': line.product_uom_qty,
                    'bultos': line.product_packaging_qty,
                    'uxb': line.product_packaging_id.qty,
                })
                #modificar las lineas de lineas de tareas asociadas a esta línea de transferencia
                for transfer_line in transfer_lines:
                    #solo actualizar las lineas de tarea que no han sido procesadas
                    line_task_lines = self.env['wms.task.line'].search([('transfer_line_id', '=', transfer_line.id), ('task_id.digip_state', '=', 'no')])
                    if line_task_lines:
                        line_task_lines.write({'quantity': line.product_uom_qty})
                transfer_line.update_qty_pending_done_invoiced()
