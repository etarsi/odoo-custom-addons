from odoo import tools, models, fields, api, _
import base64
import logging
_logger = logging.getLogger(__name__)

class StockTransfer(models.Model):
    _inherit = "stock.picking"
   #def button_validate(self):
   #    for rec in self:
   #        rec.resupply_order()
   #    res = super(StockPicking, self).button_validate()
   #    return res
    def action_assign(self):
        for rec in self:
            rec.resupply_order()
        res = super(StockPicking, self).button_validate()
        return res

    def resupply_order(self):
        for prod_id in self.move_line_ids:
            # Muevo stock a ajustes
            remote_stock_quants = self.env['stock.quant'].search([('location_id','=',22),('product_id','=',  prod_id.product_id.id)])
            remote_stock = sum(remote_stock_quants.mapped('quantity'))
            _logger.info('STOCK %s' % remote_stock)

            vals_move = {
                    'product_uom': prod_id.product_id.uom_id.id,
                    'product_id': prod_id.product_id.id,
                    'name': 'Reabastecimiento inventario %s %s'%(self.name,prod_id.display_name.strip()),
                    #'picking_type_id': 56,
                    'company_id': 2,
                    'state': 'draft',
                    'location_id': 22,
                    'location_dest_id': 79,
                    'is_inventory': True,
                    'product_uom_qty': prod_id.qty_done,
                    }
            _logger.info(vals_move)
            move_id = self.env['stock.move'].create(vals_move)
            _logger.info('MOVE X %s' % move_id)
            vals_move_line = {
                    'move_id': move_id.id,
                    'product_uom_id': prod_id.product_id.uom_id.id,
                    'product_id': prod_id.product_id.id,
                    #'lot_id': lot_id.id,
                    'company_id': 2,
                    'state': 'draft',
                    'location_id': 22,
                    'location_dest_id': 79,
                    'product_uom_qty': prod_id.qty_done,
                    'qty_done': prod_id.qty_done,
                    }
            _logger.info(vals_move_line)
            move_line_id = self.env['stock.move.line'].create(vals_move_line)
            _logger.info('MOVE XX %s' % move_line_id)
            move_id._action_done()
            # Muevo stock a Producion B
            vals_move = {
                    'product_uom': prod_id.product_id.uom_id.id,
                    'product_id': prod_id.product_id.id,
                    'name': 'Reabastecimiento inventario %s %s'%(self.name,prod_id.display_name.strip()),
                    'company_id': 1,
                    'state': 'draft',
                    'location_id': 79,
                    'location_dest_id': 8,
                    'is_inventory': True,
                    'product_uom_qty': prod_id.qty_done,
                    }
            _logger.info(vals_move)
            move_id_2 = self.env['stock.move'].create(vals_move)
            _logger.info('MOVE 2 %s' % move_id)
            vals_move_line = {
                          'move_id': move_id_2.id,
                          'product_uom_id': prod_id.product_id.uom_id.id,
                          'product_id': prod_id.product_id.id,
                          #'lot_id': lot_id.id,
                          'company_id': 1,
                          'state': 'draft',
                          'location_id': 79,
                          'location_dest_id': 8,
                          'qty_done': prod_id.qty_done,
                          }
            _logger.info(vals_move_line)
            move_line_id = self.env['stock.move.line'].create(vals_move_line)
            move_id_2._action_done()


        
