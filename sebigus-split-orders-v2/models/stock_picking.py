from odoo import tools, models, fields, api, _
import re
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"


    def split_sale_orders(self):

        original_order = self.sale_id
        _logger.info('SALE ORDER %s' % original_order)

        new_orders = self.env['sale.order']

        company_id_1 = original_order.company_default.id
        company_id_2 = int(self.env['ir.config_parameter'].sudo().get_param('sale_order_split.company_id'))
        company_ids = [company_id_1, company_id_2]

        for company_id in company_ids:
            name = self.env['res.company'].sudo().search([('id','=',company_id)]).name
            new_order_vals = {
                'name': original_order.name + str(" - ") + str(name[0]) + ' ' + self.codigo_wms,
                'partner_id': original_order.partner_id.id,
                'order_line': [],
                'company_id': company_id,
                'sale_order_template_id': original_order.sale_order_template_id.id,
                'pricelist_id': original_order.pricelist_id.id,
                'validity_date': original_order.validity_date,
                'date_order': original_order.date_order,
                'payment_term_id': original_order.payment_term_id.id,
                'picking_policy': original_order.picking_policy,
                'user_id': original_order.user_id.id,
                'splitted': 1,
                'condicion_venta': original_order.condicion_venta,
                'note': original_order.note,
                'internal_notes': original_order.internal_notes,
                'available_condiciones': False,
                'condicion_m2m': original_order.condicion_m2m.id,
                'condicion_m2m_numeric': original_order.condicion_m2m_numeric,
                'state': 'sale',
                'client_order_ref': original_order.company_id.name,
            }
            # Armos lista de producto entregados
            try:
                porcentaje =  float(original_order.condicion_m2m_numeric)
            except ValueError:
                raise UserError(_("condicion_m2m_numeric field must be a valid number."))
            entregados = {}
            for line in self.move_ids_without_package:
                entregados[line.product_id.default_code] = line.quantity_done
            for line_index, line in enumerate(original_order.order_line):
                _logger.info('CODIGO %s ' % line.product_id.default_code)
                codigo = re.sub('^9','',line.product_id.default_code)
                if codigo in entregados and entregados[codigo] > 0:
                    quantity = round(entregados[codigo] * porcentaje / 100)
                    if company_id_2 == company_id:
                        quantity = entregados[codigo] - quantity
                else:
                    quantity = 0

                # IMPUESTOS DEL PRODUCTO
                # valid_taxes = line.product_id.taxes_id.filtered(lambda tax: tax.company_id.id == company_id)
                valid_taxes = line.tax_id.filtered(lambda tax: tax.company_id.id == company_id)
                # _logger.info(f"Impuestos de línea: {valid_taxes.ids}")

                new_order_line_vals = (0, 0, {
                      'product_id': line.product_id.id,
                      'product_uom_qty': quantity,
                      'product_uom': line.product_uom.id,
                      'product_packaging_qty': quantity / line.product_packaging_id.qty,
                      'product_packaging_id': line.product_packaging_id.id,
                      'price_unit': line.price_unit,
                      'tax_id': [(6, 0, valid_taxes.ids)],
                      'discount': line.discount,
                })
                if quantity > 0:
                    new_order_vals['order_line'].append(new_order_line_vals)
                # _logger.info(f"Valores de nueva línea: {new_order_line_vals}")

            new_order = self.env['sale.order'].create(new_order_vals)
            new_orders += new_order

       #for original_line in original_order.order_line:
       #    original_quantity = original_line.product_uom_qty
       #    new_quantity = sum(line.product_uom_qty for new_order in new_orders for line in new_order.order_line if line.product_id == original_line.product_id)
       #    if abs(new_quantity - original_quantity) > 0.01:
       #        difference = original_quantity - new_quantity

       #        # POR CASO DE DIFERENCIA MAYOR A CANTIDAD ORIGINAL
       #        difference = int(-original_quantity if difference < 0 and abs(difference) > original_quantity else difference)

       #        _logger.info(f"Diferencia: {difference}")

       #        for new_order in new_orders:
       #            for line in new_order.order_line:
       #                if line.product_id == original_line.product_id:
       #                    _logger.info(f"line.product_uom_qty 1 %%%: {line.product_uom_qty}")
       #                    # VAMOS CON TRY
       #                    try:
       #                        line.product_uom_qty += difference
       #                    except Exception as e:
       #                        _logger.error(f"Error adjusting quantity for {line.product_id.name}: {e}")
       #                        continue
       #                    # line.product_uom_qty += difference
       #                    _logger.info(f"line.product_uom_qty 2 %%%: {line.product_uom_qty}")
       #                    break
       #            break

        #original_order.action_cancel()
        #original_order.toggle_active()

        for new_order in new_orders:
            new_order.write({'origin': original_order.name})

        for new_order in new_orders:
            if new_order.amount_total == 0:
                new_order.action_cancel()
                new_order.unlink()
            else:
                # Cambio  el codigo wms y el estado de envio 
                for picking in self.env['stock.picking'].search([('sale_id','=', new_order.id)]):
                    picking.write({'codigo_wms':self.codigo_wms,'state_wms':self.state_wms})
                    picking.action_assign()
                    for move in picking.move_ids_without_package:
                        move.write({'quantity_done': move.product_uom_qty})
                    picking.button_validate()


    def action_assign(self):
        for picking in self:
            # Check each move line
            if picking.company_id.id != 7:
                _logger.info('arranca desde split')
                for move in picking.move_lines:
                    product = move.product_id
                    company = picking.company_id
                    current_wh = picking.location_id.warehouse_id
                    if not current_wh:
                        current_wh = picking.location_dest_id.warehouse_id
                    current_company_location = current_wh.lot_stock_id
                    other_location = current_wh.lot_stock_id
                    available_qty = self._get_available_qty(product, current_company_location)
                    # Busco lote en la transferencia original
                    picking_ori = self.env['stock.picking'].search([('codigo_wms','=',picking.codigo_wms),('origin','=', picking.sale_id.origin)])
                    _logger.info('PKL ORI %s %s %s' % (picking_ori, picking.codigo_wms, picking.sale_id.origin) )
                    for ml in picking_ori.move_lines: 
                        for det in ml.move_line_ids:
                            if det.product_id == move.product_id:
                                lot_id = det.lot_id
                    _logger.info('PKL ORI %s %s %s %s %s %s' % (product, current_company_location, other_location,  available_qty , move.product_uom_qty, lot_id) )
                    new_lot_id = self._create_inventory_adjustment(product, current_company_location, other_location,  available_qty , move.product_uom_qty, lot_id)
            res = super(StockPicking, self).action_assign()

 

