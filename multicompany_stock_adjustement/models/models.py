from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

#    def check_available(self):
    def action_assign(self):
        _logger.info('arranca.....')
        res = None
        all_wh = self.env['stock.warehouse'].search([])
        for picking in self:
            # Check each move line
            for move in picking.move_lines:
                product = move.product_id
                company = picking.company_id
                current_wh = picking.location_id.warehouse_id
                if not current_wh:
                    current_wh = picking.location_dest_id.warehouse_id
                current_company_location = current_wh.lot_stock_id
                _logger.info(('current_company_location...',current_company_location.complete_name,company,current_company_location))
                # Check availability in the current company
                available_qty = self._get_available_qty(product, current_company_location)
                _logger.info(('available...',product.default_code,available_qty))
                if move.quantity_done > 0 and available_qty < move.quantity_done:
                    # If not enough in the current company, check other companies
                    for other_wh in self.env['stock.warehouse'].search([('id', '!=', current_wh.id)]):
                        other_location = other_wh.lot_stock_id
                        other_available_qty = self._get_available_qty(product, other_location)
                        _logger.info(('other_location...',product.default_code,other_location.complete_name,other_available_qty, current_company_location,current_wh))
                        if other_available_qty > 0:
                            # Create inventory adjustments
                            lot_id = self._create_inventory_adjustment(product, other_location, current_company_location, other_available_qty , move.quantity_done * -1 )
                           #if not lot_id:
                           #    raise ValidationError('Error lote con stock %s %s %s  %s %s' % (move.product_id.default_code,other_location.display_name,current_company_location.display_name,other_available_qty,move.quantity_done))
                            new_lot_id = self._create_inventory_adjustment(product, current_company_location, other_location,  available_qty , move.quantity_done, lot_id)
                            continue
                         #  for i in move.move_line_ids:
    #                    #      raise ValidationError('Nuevo lote con stock in digip %s %s . ' % (new_lot_id.id,new_lot_id.name))
                         #      i.write({'lot_id': new_lot_id.id })

           ## Verifico si todos los lotes que estan en los detalles, corresponden a la empresa
           #for move in picking.move_lines:
           #    current_wh = picking.location_id.warehouse_id
           #    current_company_location = current_wh.lot_stock_id
           #    if move.quantity_done > 0:
           #        for i in  move.move_line_ids:
           #            if i.lot_id and i.lot_id.company_id != current_company_location.company_id:
           #                # si el lote que esta selecciondo no es de la compania lo cambio
           #                domain = [
           #                    ('name', '=', i.lot_id.name),
           #                    ('company_id', '=', current_company_location.company_id.id),
           #                ]
           #                new_lot_id = self.env['stock.production.lot'].search(domain)
           #                i.write({'lot_id': new_lot_id.id })
           #                #raise ValidationError('Error lote con stock %s %s %s  %s %s %s ' % (move.product_id.default_code,i.lot_id.id,i.lot_id.name,i.lot_id.company_id,current_company_location.company_id, new_lot_id.id))
            # Almaceno las unidades solicitadas
            pedido = {}
            for move in picking.move_lines:
                if move.quantity_done > 0:
                    pedido[move.product_id.default_code] = move.quantity_done
            # Despues de realizar los ajustes anulo la reserva
            self.env['stock.move.line'].search([('picking_id','=', picking.id)]).unlink()
           ## Vuelvo a realizar la asignacion de stock
            res = super(StockPicking, self).action_assign()
           ## Vuelvo a marcar las unidades pedidas
           #for det in picking.move_ids_without_package: 
           #    if det.product_id.default_code in pedido:
           #        det.write({'quantity_done': pedido[det.product_id.default_code],'forecast_availability': pedido[det.product_id.default_code] })
            for ml in picking.move_lines: 
                for det in ml.move_line_ids:
                    if det.product_id.default_code in pedido:
                        det.write({'qty_done': pedido[det.product_id.default_code] })
                        del(pedido[det.product_id.default_code])
                if ml.product_id.default_code in pedido:
                    ml.write({'quantity_done': pedido[ml.product_id.default_code],'forecast_availability': pedido[ml.product_id.default_code] })
                    del(pedido[ml.product_id.default_code])
            # Si queda mal un lote lo modifico
            self.actualizo_lotes()
        return  res

    def _get_available_qty(self, product, location):
        """Get available quantity of a product at a given location."""
        domain = [
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
            ('quantity', '>', 0),
        ]
        inventory_lines = self.env['stock.quant'].search(domain)
        #return sum(line.quantity - line.reserved_quantity for line in inventory_lines)
        return sum(line.quantity for line in inventory_lines)

    def _create_inventory_adjustment(self, product, location, from_location,  qty, dif,lot_id = None):
        # Consulto el stock para buscar el lote
        # Create a new inventory adjustment
        inventory = self.env['stock.inventory'].create({
            'name': f"{location.complete_name} -> {from_location.name} ({self.name} {product.default_code} {dif} )",
            'product_selection': 'one',
            'location_ids': [location.id],
            'product_ids': [product.id],
        })

        inventory.action_state_to_in_progress()

        if dif < 0:
            _logger.info('GENERO DESCUENTO DE STOCK %s %s' % (location.name,product.display_name))
           #domain = [
           #    ('product_id', '=', product.id),
           #    ('location_id', '=', location.id),
           #    ('quantity', '>', 0),
           #]
           #inventory_lines = self.env['stock.quant'].search(domain)
           #for inv in inventory_lines:
           #    if inv.quantity > (dif * -1):
           #        lot_id = inv.lot_id
           #        qty = inv.quantity + dif
           #        continue
           #lot_id = inv.lot_id
            _logger.info('GENERO BAJA %s  %s' % (inventory , len(inventory.stock_quant_ids)) )

            for inventory_line in inventory.stock_quant_ids:
                _logger.info('GENERO AJUSTE %s %s %s %s ' % (inventory_line,inventory_line.quantity , dif,inventory_line.lot_id) )
                if inventory_line.quantity > (dif * -1):
                    inventory_line.write({'inventory_quantity': inventory_line.quantity + dif})
                    lot_id = inventory_line.lot_id
                    inventory_line._apply_inventory()
                _logger.info('GENERO AJUSTE %s %s %s %s  %s' % (inventory_line,inventory_line.quantity , dif,inventory_line.lot_id,lot_id) )
        else:
            if not lot_id:
                # Busco un lote para el producto
                domain = [
                    ('product_id', '=', product.id),
                    ('company_id', '=', location.company_id.id),
                ]
                new_lot_id = self.env['stock.production.lot'].search(domain)
                if not new_lot_id:
                    domain = [
                        ('product_id', '=', product.id),
                    ]
                    new_lot_id = self.env['stock.production.lot'].search(domain)
                    if not new_lot_id:
                        raise ValidationError('No hay lotes para el producto  %s' % product.default_code)
                    else:
                        lot_id = new_lot_id[0]
                else:
                    lot_id = new_lot_id[0]
            # Busco el lote para el producto a transferir
            domain = [
                ('name', '=', lot_id.name),
                ('company_id', '=', location.company_id.id),
            ]
            new_lot_id = self.env['stock.production.lot'].search(domain)
            if not new_lot_id:
                # creo un lote nuevo
                new_lot_id = self.env['stock.production.lot'].create({'name':lot_id.name,
                                                                      'product_id':lot_id.product_id.id,
                                                                      'ref':lot_id.ref,
                                                                      'dispatch_number':lot_id.dispatch_number,
                                                                      'company_id': location.company_id.id})

            _logger.info('GENERO ALTA %s  %s' % (inventory , len(inventory.stock_quant_ids)) )

            for inventory_line in inventory.stock_quant_ids:
                _logger.info('GENERO AJUSTE %s %s %s %s ' % (inventory_line,inventory_line.quantity , dif,inventory_line.lot_id) )
                if inventory_line.quantity > 0:
                    dif_update = inventory_line.quantity + dif
                else:
                    dif_update = dif
                inventory_line.write({'inventory_quantity': dif_update})
                inventory_line._apply_inventory()
            if  len(inventory.stock_quant_ids) == 0:
                _logger.info('Creo una nueva linea de sotkc lote %s %s' % (product.default_code,lot_id.name))
                # Si no hay stock, creo una nueva linea
                 #try:
                if True:
                    inventory_line = self.env['stock.quant'].create({
                            'current_inventory_id': inventory.id,
                            'location_id': location.id,
                            'lot_id': new_lot_id.id,
                            'product_id': product.id,
                            'inventory_quantity': dif,
                            'product_uom_id': product.uom_id.id, })
                    inventory_line._apply_inventory()
               #except Exception as error:
               #    vals = {
               #            'inventory_id': inventory.id,
               #            'location_id': location.id,
               #            'lot_id': new_lot_id.id,
               #            'product_id': product.id,
               #            'inventory_quantity': dif,
               #            'product_uom_id': product.uom_id.id, }
               #    _logger.info('No se pudo realizar el ajuste %s  %s' % (vals, error) )
                lot_id = new_lot_id

        inventory.action_state_to_done()
        return lot_id



#   def _create_inventory_adjustment(self, product_id, location_id, current_location, new_quantity):
#       _logger.info('CREO AJUSTE %s %s %s %s' %  (product_id, location_id, current_location,  new_quantity))
#       # Create a new inventory adjustment
#       inventory_adjustment = self.env['stock.inventory'].create({
#           'name': f"{location_id.complete_name} -> {current_location.name} ({self.name})",
#           'location_id': location_id,
#           'product_id': product_id,
#       })

#       # Add the inventory line
#       inventory_line = self.env['stock.inventory.line'].create({
#           'inventory_id': inventory_adjustment.id,
#           'product_id': product_id,
#           'location_id': location_id,
#           'product_qty': new_quantity,
#           'product_uom_id': self.env.ref('product_id.product_uom_unit').id,
#           'theoretical_qty': new_quantity,
#       })

#       # Confirm the inventory adjustment
#       inventory_adjustment.action_start()
#       inventory_adjustment.action_validate()

#       return inventory_adjustment

#   def _create_inventory_adjustment(self, product, location, current_location,  qty):
#       quant = self.env['stock.quant'].search([('location_id','=',location.id),('product_id','=',product.id)],limit=1)
#       if quant:
#           quant.write({'quantity':qty})
#       else:
#           inventory = self.env['stock.quant'].create({
#               'location_ids': location.id,
#               'product_id': product.id,
#               'quantity': qty,
#               'product_uom_id': product.uom_id.id,
#           }),
#           inventory.action_state_to_done()

    def actualizo_lotes(self):
       for move in self.move_lines:
           current_wh = self.location_id.warehouse_id
           if not current_wh:
               current_wh = self.location_dest_id.warehouse_id
           current_company_location = current_wh.lot_stock_id
           if move.quantity_done > 0:
               for i in  move.move_line_ids:
                   if i.lot_id and i.lot_id.company_id != current_company_location.company_id:
                       # si el lote que esta selecciondo no es de la compania lo cambio
                       domain = [
                           ('name', '=', i.lot_id.name),
                           ('company_id', '=', current_company_location.company_id.id),
                       ]
                       new_lot_id = self.env['stock.production.lot'].search(domain)
                       if not new_lot_id:
                           domain = [
                               ('product_id', '=', i.product_id.id),
                           ]
                           lot_id_ori = self.env['stock.production.lot'].search(domain)
                           lot_id = lot_id_ori[0]
                           new_lot_id = self.env['stock.production.lot'].create({'name':lot_id.name,
                                                                      'product_id':lot_id.product_id.id,
                                                                      'ref':lot_id.ref,
                                                                      'dispatch_number':lot_id.dispatch_number,
                                                                      'company_id': current_company_location.company_id.id})
                           lot_id = new_lot_id
                       else:
                           new_lot_id = new_lot_id[0]
                       i.write({'lot_id': new_lot_id.id })
                   else:
                        #Busco un lote para el producto y se lo cargo
                       domain = [
                           ('product_id', '=', i.product_id.id),
                           ('company_id', '=', current_company_location.company_id.id),
                       ]
                       new_lot_id = self.env['stock.production.lot'].search(domain)
                       _logger.info('LOTE %s %s' % (new_lot_id,i.product_id.default_code) )
                       if not new_lot_id:
                           domain = [
                               ('product_id', '=', i.product_id.id),
                           ]
                           lot_id_ori = self.env['stock.production.lot'].search(domain)
                           _logger.info('LOTE 2 %s %s' % (new_lot_id,i.product_id.default_code) )
                           if not lot_id_ori:
                                raise ValidationError('No hay lotes para el producto  %s' % i.product_id.default_code)

                           lot_id = lot_id_ori[0]
                           new_lot_id = self.env['stock.production.lot'].create({'name':lot_id.name,
                                                                      'product_id':lot_id.product_id.id,
                                                                      'ref':lot_id.ref,
                                                                      'dispatch_number':lot_id.dispatch_number,
                                                                      'company_id': current_company_location.company_id.id})
                           lot_id = new_lot_id
                       else:
                           lot_id = new_lot_id[0]
                        
                       i.write({'lot_id': lot_id.id })

