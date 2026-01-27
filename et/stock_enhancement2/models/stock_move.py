from odoo import models, fields, api, _
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
import logging
import math
import requests
from itertools import groupby
from datetime import timedelta

class StockMoveInherit(models.Model):
    _inherit = "stock.move"

    product_available_percent = fields.Float(string='Porc Disponible', compute='_calculate_bultos', store=True, group_operator='avg')
    product_packaging_qty = fields.Float(string='Bultos', compute='_calculate_bultos', store=True)
    product_available_pkg_qty = fields.Float(string='Bultos Disponibles', compute='_calculate_bultos', store=True)

    availability = fields.Char(string="Disponible")
    license = fields.Char(string="Licencia", related='picking_id.carrier_tracking_ref', store=True)

    @api.depends('quantity_done', 'product_uom_qty')
    def _calculate_bultos(self):
        for record in self:
            if record.product_uom_qty > 0:
                record.product_available_percent = (record.quantity_done * 100) / record.product_uom_qty

    @api.model_create_multi   
    def create(self, vals):
        move = super(StockMoveInherit, self).create(vals)
        #verificar si el product_id viene con el default_code como primer caracter 9
        if 'product_id' in vals:
            product = self.env['product.product'].browse(vals['product_id'])
            if product.default_code and product.default_code[0] == '9':
                # asigno un product con default_code quitando el 9 y buscar ese codigo
                new_code = product.default_code[1:]
                new_product = self.env['product.product'].search([('default_code', '=', new_code)], limit=1)
                if new_product:
                    move.product_id = new_product
                else:
                    raise ValidationError(_("No se encontró un producto con el código %s") % new_code)
        return move
    

    def write(self, vals):
        res = super(StockMoveInherit, self).write(vals)
        for record in self:
            if 'product_id' in vals:
                product = self.env['product.product'].browse(vals['product_id'])
                if product.default_code and product.default_code[0] == '9':
                    new_code = product.default_code[1:]
                    new_product = self.env['product.product'].search([('default_code', '=', new_code)], limit=1)
                    if new_product:
                        record.product_id = new_product
                    else:
                        raise ValidationError(_("No se encontró un producto con el código %s") % new_code)
        return res