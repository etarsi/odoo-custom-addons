from odoo import _, models, fields, api
import json
from odoo.exceptions import UserError, ValidationError
import logging
import requests
from requests.structures import CaseInsensitiveDict
import re
null=None

_logger = logging.getLogger(__name__)


class InventoryAdjustment(models.Model):
    _inherit = 'stock.quant'

    def create_inventory_adjustment(self, product_id, location_id, new_quantity):
        # Create a new inventory adjustment
        inventory_adjustment = self.env['stock.inventory'].create({
            'name': 'Ajuste de Inventario DigipWMS - [{product.default_code}]{product.name})',
            'filter': 'product',
            'location_id': location_id,
            'product_id': product_id,
        })

        # Add the inventory line
        inventory_line = self.env['stock.inventory.line'].create({
            'inventory_id': inventory_adjustment.id,
            'product_id': product_id,
            'location_id': location_id,
            'product_qty': new_quantity,
            'product_uom_id': self.env.ref('product.product_uom_unit').id,
            'theoretical_qty': new_quantity,
        })

        # Confirm the inventory adjustment
        inventory_adjustment.action_start()
        inventory_adjustment.action_validate()

        return inventory_adjustment



class Product(models.Model):
    _inherit = 'product.product'

    def adjust_inventory_for_difference(self, location_origin ,location_dest):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get(f'{url}/v1/Stock', headers=headers)
        if respGet.status_code not in [200, 201] or respGet.content.strip() == b'null':
            return False

        json_response = respGet.json()

        companies = self.env['res.company'].search([])

        for company in companies:
            warehouse_stamped = self.env['stock.location'].search([
                ('company_id', '=', company.id),
                ('usage', '=', 'internal'),
                ('name', 'ilike', location_origin)
            ], limit=1)
            warehouse_stock = self.env['stock.warehouse'].search([
                ('company_id', '=', company.id),
                ('lot_stock_id.usage', '=', 'internal'),
                ('lot_stock_id.complete_name', 'ilike', location_dest)
            ], limit=1)

            if not warehouse_stamped or not warehouse_stock:
                continue

            location_stamped = warehouse_stamped
            location_stock = warehouse_stock.lot_stock_id

            if 'UnidadesBloqueadas' in json_response:
                for product_data in json_response['UnidadesBloqueadas']:
                    product = self.env['product.product'].search([('default_code', '=', product_data['CodigoArticulo'])], limit=1)
                    if not product:
                        continue

                    available_qty = product_data['UnidadesBloqueadas']
                    # Get the quantity available only in the Estampillado location
                    quant_stamped = self.env['stock.quant'].search([
                         ('product_id', '=', product.id),
                         ('location_id', '=', location_stamped.id)
                    ])
                    if quant_stamped:
                        stamped_qty = quant_stamped.quantity

                    _logger.info(('product...',product,diff_qty,stamped_qty))
                    diff_qty = stamped_qty - available_qty

                    if diff_qty != 0:
                        inventory_adjustment = InventoryAdjustment.create_inventory_adjustment(product, location_stock, diff_qty)

                    # Update quantities in the Estampillado location
                    quant_stamped = self.env['stock.quant'].search([
                        ('product_id', '=', product.id),
                        ('location_id', '=', location_stamped.id)
                    ])
                    if quant_stamped:
                        quant_stamped.write({'quantity': available_qty})

                    # Update quantities in the Stock location
                    quant_stock = self.env['stock.quant'].search([
                        ('product_id', '=', product.id),
                        ('location_id', '=', location_stock.id)
                    ])
                    if quant_stock:
                        new_quantity = quant_stock.quantity + diff_qty
                        quant_stock.write({'quantity': quant_stock + diff_qty})

        return True




    def adjust_inventory_for_difference_unit(self, location_origin ,location_dest):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get(f'{url}/v1/Stock', headers=headers)
        if respGet.status_code not in [200, 201] or respGet.content.strip() == b'null':
            return False

        json_response = respGet.json()

        companies = self.env['res.company'].search([])

        for company in companies:
            warehouse_stamped = self.env['stock.warehouse'].search([
                ('company_id', '=', company.id),
                ('lot_stock_id.usage', '=', 'internal'),
                ('lot_stock_id.complete_name', 'ilike', location_origin)
            ], limit=1)
            warehouse_stock = self.env['stock.warehouse'].search([
                ('company_id', '=', company.id),
                ('lot_stock_id.usage', '=', 'internal'),
                ('lot_stock_id.complete_name', 'ilike', location_dest)
            ], limit=1)

            if not warehouse_stamped or not warehouse_stock:
                continue


            location_stamped = warehouse_stamped.lot_stock_id
            location_stock = warehouse_stock.lot_stock_id

            if 'UnidadesBloqueadas' in json_response:
                for product_data in json_response['UnidadesBloqueadas']:
                    product = self.env['product.product'].search([('default_code', '=', product_data['CodigoArticulo'])], limit=1)
                    if not product:
                        continue

                    available_qty = product_data['UnidadesBloqueadas']
                    # Get the quantity available only in the Estampillado location
                    quant_stamped = self.env['stock.quant'].search([
                         ('product_id', '=', product.id),
                         ('location_id', '=', location_stamped.id)
                    ])
                    if quant_stamped:
                        stamped_qty = quant_stamped.quantity

                    diff_qty = stamped_qty - available_qty

                    if diff_qty != 0:
                        inventory_adjustment = InventoryAdjustment.create_inventory_adjustment(product, location_stock, diff_qty)

                    # Update quantities in the Estampillado location
                    quant_stamped = self.env['stock.quant'].search([
                        ('product_id', '=', product.id),
                        ('location_id', '=', location_stamped.id)
                    ])
                    if quant_stamped:
                        quant_stamped.write({'quantity': available_qty})

                    # Update quantities in the Stock location
                    quant_stock = self.env['stock.quant'].search([
                        ('product_id', '=', product.id),
                        ('location_id', '=', location_stock.id)
                    ])
                    if quant_stock:
                        new_quantity = quant_stock.quantity + diff_qty
                        quant_stock.write({'quantity': quant_stock + diff_qty})

        return True
