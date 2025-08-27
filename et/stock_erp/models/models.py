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

    move_lines = fields.One2many('stock.moves.erp', 'stock_erp')
    product_id = fields.Many2one('product.template', string='Producto', required=True)
    product_name = fields.Char(string='Producto')
    uxb = fields.Integer('UxB', default=0)

    fisico_unidades = fields.Integer('Físico Unidades')
    enelagua_unidades = fields.Integer('En el Agua Unidades')
    total_unidades = fields.Integer('Total Unidades', compute="_compute_total")
    comprometido_unidades = fields.Integer('Comprometido Unidades')
    disponible_unidades = fields.Float('Disponible Unidades', digits=(99,0))
    comprado_unidades = fields.Integer('Comprado Unidades')
    entrante_unidades = fields.Integer('Entrante Unidades')

    fisico_bultos = fields.Float('Físico Bultos', compute="_compute_fisico_bultos")
    enelagua_bultos = fields.Float('En el Agua Bultos', compute="_compute_enelagua_bultos")    
    total_bultos = fields.Float('Total Bultos', compute="_compute_total")
    comprometido_bultos = fields.Float('Comprometido Bultos', compute="_compute_comprometido_bultos")
    disponible_bultos = fields.Float('Disponible Bultos', compute="_compute_disponible_bultos")
    comprado_bultos = fields.Float('Comprado Bultos', compute="_compute_comprado_bultos")
    entrante_bultos = fields.Float('Entrante Bultos', compute="_compute_entrante_bultos")

    entrante_fecha = fields.Date('ETA')
    entrante_licencia = fields.Char('Licencia')


    def get_stock_wms(self):
        for record in self:
            stock_wms = self.env['stock.wms'].search([('product_id', '=', record.product_id.id)], limit=1)

            if stock_wms:
                record.fisico_unidades = stock_wms.fisico_unidades


    def create_initial_products(self):
        stock_wms = self.env['stock.wms']
        stock_erp = self.env['stock.erp']
        stock_wms_records = stock_wms.search([])
        vals_list = []

        for record in stock_wms_records:
            vals = {
                'product_id': record.product_id.id,
                'uxb': int(record.uxb),
                'fisico_unidades': record.fisico_unidades,
            }
            vals_list.append(vals)
        stock_erp.create(vals_list)


    #####  COMPUTE METHODS #####

    def update_uxb(self):
        for record in self:
            if record.product_id.packaging_ids:
                record.uxb = record.product_id.packaging_ids[0].qty


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