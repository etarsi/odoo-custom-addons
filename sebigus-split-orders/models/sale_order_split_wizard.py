from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class SaleOrderSplitWizard(models.TransientModel):
    _name = 'sale.order.split.wizard'
    _description = 'Sale Order Split Wizard'

    percentage = fields.Float(
        string='Porcentaje (%)',
        digits=(10, 2),
        required=True,
        default=lambda self: self._default_percentage()
    )
    
    old_sale = fields.Boolean()

    def _default_percentage(self):
        sale_order_id = self._context.get('active_id')
        sale_order = self.env['sale.order'].browse(sale_order_id)
        if sale_order and sale_order.condicion_m2m_numeric:
            try:
                return float(sale_order.condicion_m2m_numeric)
            except ValueError:
                raise UserError(_("condicion_m2m_numeric field must be a valid number."))
        raise UserError(_("Por favor seleccioná una Condición de Venta."))
        # PARA ESTABLECER UN VALOR POR DEFECTO return 0.0

    def action_split_sale_orders(self):

        original_order = self.env['sale.order'].browse(self._context.get('active_id'))

        if original_order.splitted:
            raise UserError(_("La Orden de Venta original ya está dividida."))

        new_orders = self.env['sale.order']

        company_id_1 = original_order.company_id.id
        company_id_2 = int(self.env['ir.config_parameter'].sudo().get_param('sale_order_split.company_id'))
        company_ids = [company_id_1, company_id_2]

        for company_id in company_ids:
            name = self.env['res.company'].sudo().search([('id','=',company_id)]).name
            new_order_vals = {
                'name': original_order.name + str(" - ") + str(name[0]),
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
            # _logger.info(f"Nueva SO: {new_order_vals}")

            for line_index, line in enumerate(original_order.order_line):
                quantity = round(line.product_uom_qty * self.percentage / 100)

                # IMPUESTOS DEL PRODUCTO
                # valid_taxes = line.product_id.taxes_id.filtered(lambda tax: tax.company_id.id == company_id)
                valid_taxes = line.tax_id.filtered(lambda tax: tax.company_id.id == company_id)
                # _logger.info(f"Impuestos de línea: {valid_taxes.ids}")

                new_order_line_vals = (0, 0, {
                      'product_id': line.product_id.id,
                      'product_uom_qty': quantity,
                      'product_uom': line.product_uom.id,
                      #'product_packaging_qty': quantity / line.product_packaging_id.qty if line.product_packaging_id else 0,
                      'product_packaging_qty': line.product_packaging_qty,
                      'product_packaging_id': line.product_packaging_id.id,
                      'price_unit': line.price_unit,
                      'tax_id': [(6, 0, valid_taxes.ids)],
                      'discount': line.discount,
                })
                new_order_vals['order_line'].append(new_order_line_vals)
                # _logger.info(f"Valores de nueva línea: {new_order_line_vals}")

            new_order = self.env['sale.order'].create(new_order_vals)
            new_orders += new_order

        for original_line in original_order.order_line:
            original_quantity = original_line.product_uom_qty
            new_quantity = sum(line.product_uom_qty for new_order in new_orders for line in new_order.order_line if line.product_id == original_line.product_id)
            if abs(new_quantity - original_quantity) > 0.01:
                difference = original_quantity - new_quantity

                # POR CASO DE DIFERENCIA MAYOR A CANTIDAD ORIGINAL
                difference = int(-original_quantity if difference < 0 and abs(difference) > original_quantity else difference)

                _logger.info(f"Diferencia: {difference}")

                for new_order in new_orders:
                    for line in new_order.order_line:
                        if line.product_id == original_line.product_id:
                            _logger.info(f"line.product_uom_qty 1 %%%: {line.product_uom_qty}")
                            # VAMOS CON TRY
                            try:
                                line.product_uom_qty += difference
                            except Exception as e:
                                _logger.error(f"Error adjusting quantity for {line.product_id.name}: {e}")
                                continue
                            # line.product_uom_qty += difference
                            _logger.info(f"line.product_uom_qty 2 %%%: {line.product_uom_qty}")
                            break
                    break

        # ESTO NO SIRVE CON EL BOTÓN DE CONFIRMACIÓN, PORQUE PRIMERO CONFIRMA,
        # ENTONCES LUEGO NO PUEDE ELIMINAR: COMENTAMOS LÍNEAS
        # for new_order in new_orders:
        #     for line in new_order.order_line:
        #         if line.product_uom_qty == 0:
        #             new_order.write({'order_line': [(3, line.id)]})

        original_order.action_cancel()
        original_order.toggle_active()

        for new_order in new_orders:
            new_order.write({'origin': original_order.name})

        for new_order in new_orders:
            if new_order.amount_total == 0:
                new_order.action_cancel()
                new_order.unlink()

        return {
            'type': 'ir.actions.act_window',
            'name': 'New Sale Orders',
            'res_model': 'sale.order',
            # 'res_id': original_order.id,
            'view_mode': 'tree,form',
            # 'target': 'current',
        }

