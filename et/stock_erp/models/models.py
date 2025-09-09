from odoo import models, fields, api, _
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError, AccessError
import logging
import math
import requests
from itertools import groupby
from datetime import timedelta

class StockERP(models.Model):
    _name = 'stock.erp'

    name = fields.Char(compute='_compute_name')
    move_lines = fields.One2many('stock.moves.erp', 'stock_erp')
    move_lines_reserved = fields.One2many('stock.moves.erp', compute="_compute_move_lines_reserved", store=False)
    move_lines_delivered = fields.One2many('stock.moves.erp', compute="_compute_move_lines_delivered", store=False)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    product_code = fields.Char(string="Código", compute="_compute_product_info", store=True)
    product_name = fields.Char(string='Producto', compute="_compute_product_info", store=True)
    product_category = fields.Many2one('product.category', string="Categoría", compute="_compute_category_id", store=True)
    uxb = fields.Integer('UxB', default=0)

    fisico_unidades = fields.Integer('Físico Unidades')
    enelagua_unidades = fields.Integer('En el Agua Unidades')
    total_unidades = fields.Integer('Total Unidades', compute="_compute_total", store=True)
    comprometido_unidades = fields.Integer('Comprometido Unidades', compute="_compute_comprometido_unidades", store=True)
    disponible_unidades = fields.Float('Disponible Unidades', digits=(99,0), compute="_compute_disponible_unidades", store=True)
    comprado_unidades = fields.Integer('Comprado Unidades')
    entrante_unidades = fields.Integer('Entrante Unidades')

    fisico_bultos = fields.Float('Físico Bultos', compute="_compute_fisico_bultos", store=True)
    enelagua_bultos = fields.Float('En el Agua Bultos', compute="_compute_enelagua_bultos", store=True)    
    total_bultos = fields.Float('Total Bultos', compute="_compute_total", store=True)
    comprometido_bultos = fields.Float('Comprometido Bultos', compute="_compute_comprometido_bultos", store=True)
    disponible_bultos = fields.Float('Disponible Bultos', compute="_compute_disponible_bultos", store=True)
    comprado_bultos = fields.Float('Comprado Bultos', compute="_compute_comprado_bultos", store=True)
    entrante_bultos = fields.Float('Entrante Bultos', compute="_compute_entrante_bultos", store=True)

    entrante_fecha = fields.Date('ETA')
    entrante_licencia = fields.Char('Licencia')


    def create_initial_products(self):

        stock_digip = self.get_digip_stock()
        stock_erp = self.env['stock.erp']
        vals_list = []

        for record in stock_digip:
            product_id = self.env['product.product'].search([('default_code', '=', record['codigo'])], limit=1)
            if product_id:
                uxb = self.get_uxb(product_id.product_tmpl_id)
                vals = {
                    'product_id': product_id.id,
                    'uxb': uxb,
                    'fisico_unidades': record['stock']['disponible']
                }
                vals_list.append(vals)
        stock_erp.create(vals_list)
    

    def get_digip_stock(self):
        headers = {}
        
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms-v2.url')
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        response = requests.get(f'{url}/v2/Stock/Tipo', headers=headers)

        if response.status_code == 200:
            products = response.json()
            if products:
                return products

        elif response.status_code == 400:
            raise UserError('ERROR: 400 BAD REQUEST. Avise a su administrador de sistema.')
        elif response.status_code == 404:
            raise UserError('ERROR: 404 NOT FOUND. Avise a su administrador de sistema.')
        elif response.status_code == 500:
            raise UserError('ERROR: 500 INTERNAL SERVER ERROR. Avise a su administrador de sistema. Probablemente alguno de los productos no se encuentra creado en Digip.')     
    

    def get_stock_wms(self):
        for record in self:
            stock_wms = self.env['stock.wms'].search([('product_id', '=', record.product_id.id)], limit=1)

            if stock_wms:
                record.fisico_unidades = stock_wms.fisico_unidades


    def update_uxb(self):
        for record in self:
            if record.product_id.product_tmpl_id.packaging_ids:
                record.uxb = record.product_id.product_tmpl_id.packaging_ids[0].qty

    def get_uxb(self, product_product_id):
        product_id = self.env['product.template'].browse(product_product_id.id)

        if product_id:
            if product_id.packaging_ids:
                return product_id.packaging_ids[0].qty
            
    def increase_fisico_unidades(self, quantity):
        for record in self:
            record.fisico_unidades += quantity

    
    def increase_comprometido_unidades(self, quantity):
        for record in self:
            record.comprometido_unidades += quantity


    def decrease_fisico_unidades(self, quantity):
        for record in self:
            if quantity <= record.fisico_unidades:
                record.fisico_unidades -= quantity
            else: 
                raise UserError(f'Para el product: {record.product_id}, tiene {record.fisico_unidades} unidades y quiere entregar {quantity} unidades. El resultado no puede ser negativo')
            
            
    def decrease_comprometido_unidades(self, quantity):
        for record in self:
            if quantity <= record.comprometido_unidades:
                record.comprometido_unidades -= quantity
            else: 
                raise UserError(f'Para el product: {record.product_id}, tiene {record.comprometido_unidades} unidades y quiere liberar {quantity} unidades. El resultado no puede ser negativo')


    #####  COMPUTE METHODS #####

    @api.depends('product_id')
    def _compute_product_info(self):
        for record in self:
            if record.product_id:
                record.product_code = record.product_id.default_code
                record.product_name = record.product_id.name
            
    @api.depends('move_lines')
    def _compute_move_lines_reserved(self):
        for record in self:
            record.move_lines_reserved = record.move_lines.filtered(
                lambda l: l.type == 'reserve')


    @api.depends('move_lines')
    def _compute_move_lines_delivered(self):
        for record in self:
            record.move_lines_delivered = record.move_lines.filtered(
                lambda l: l.type == 'delivery')


    @api.depends('product_id')
    def _compute_name(self):
        for record in self:
            if record.product_id:
                record.name = record.product_id.name
            else: record.name = record.id

    # @api.depends('move_lines')
    # def _compute_comprometido_unidades(self):
    #     for record in self:
    #         record.comprometido_unidades = sum(
    #             line.quantity for line in record.move_lines if line.type == 'reserve'
    #         )

    @api.depends('fisico_unidades', 'enelagua_unidades', 'comprometido_unidades')
    def _compute_disponible_unidades(self):
        for record in self:
            record.disponible_unidades = record.fisico_unidades + record.enelagua_unidades - record.comprometido_unidades


    @api.depends('product_id')
    def _compute_category_id(self):
        for record in self:
            if record.product_id:
                record.product_category = record.product_id.categ_id.parent_id.id

    @api.depends('fisico_unidades', 'uxb')
    def _compute_fisico_bultos(self):
        for record in self:
            if record.uxb:
                record.fisico_bultos = record.fisico_unidades / record.uxb
            else: record.fisico_bultos = 0
    
    
    @api.depends('enelagua_unidades', 'uxb')
    def _compute_enelagua_bultos(self):
        for record in self:
            if record.uxb:
                record.enelagua_bultos = record.enelagua_unidades / record.uxb
            else: record.enelagua_bultos = 0
    

    @api.depends('fisico_unidades', 'enelagua_unidades')
    def _compute_total(self):
        for record in self:
            record.total_unidades = record.fisico_unidades + record.enelagua_unidades

            if record.uxb:
                record.total_bultos = record.total_unidades / record.uxb
            else: record.total_bultos = 0
  
    
    @api.depends('comprometido_unidades')
    def _compute_comprometido_bultos(self):
        for record in self:
            if record.uxb:
                record.comprometido_bultos = record.comprometido_unidades / record.uxb
            else: record.comprometido_bultos = 0
    

    @api.depends('disponible_unidades')
    def _compute_disponible_bultos(self):
        for record in self:
            if record.uxb:
                record.disponible_bultos = record.disponible_unidades / record.uxb
            else: record.disponible_bultos = 0
    
    
    @api.depends('comprado_unidades')
    def _compute_comprado_bultos(self):
        for record in self:
            if record.uxb:
                record.comprado_bultos = record.comprado_unidades / record.uxb
            else: record.comprado_bultos = 0


    @api.depends('entrante_unidades')
    def _compute_entrante_bultos(self):
        for record in self:
            if record.uxb:
                record.entrante_bultos = record.entrante_unidades / record.uxb
            else: record.entrante_bultos = 0


    ##### DEBUG METHODS #####

    def set_to_zero(self):
        self.fisico_unidades = 0