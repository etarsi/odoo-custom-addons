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

    move_lines = fields.One2many('stock.moves.erp')
    product_id = fields.Many2one('product.template', string='Producto', required=True)
    product_name = fields.Char(string='Producto')
    uxb = fields.Integer('UxB')

    fisico_unidades = fields.Integer('Físico Unidades')
    enelagua_unidades = fields.Integer('En el Agua Unidades')
    total_unidades = fields.Integer('Total Unidades')
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
                'uxb': record.uxb,
                'fisico_unidades': record.fisico_unidades,
            }
            vals_list.append(vals)
        stock_erp.create(vals_list)


    #####  COMPUTE METHODS #####

    @api.depends('product_id')
    def _compute_uxb(self):
        for record in self:
            if record.product_id:
                if record.product_id.packaging_ids:
                    record.uxb = record.product_id.packaging_ids[0].qty


    def update_uxb(self):
        for record in self:
            if record.product_id.packaging_ids:
                record.uxb = record.product_id.packaging_ids[0].qty


    @api.depends('fisico_unidades', 'uxb')
    def _compute_fisico_bultos(self):
        if self.uxb:
            self.fisico_bultos = self.fisico_unidades / self.uxb
    
    
    @api.depends('enelagua_unidades', 'uxb')
    def _compute_enelagua_bultos(self):
        if self.uxb:
            self.enelagua_bultos = self.enelagua_unidades / self.uxb
    

    @api.depends('fisico_unidades', 'enelagua_unidades')
    def _compute_total(self):
        self.total_unidades = self.fisico_unidades + self.enelagua_unidades

        if self.uxb:
            self.total_bultos = self.total_unidades / self.uxb
  
    
    @api.depends('comprometido_unidades')
    def _compute_comprometido_bultos(self):
        if self.uxb:
            self.comprometido_bultos = self.comprometido_unidades / self.uxb
    

    @api.depends('disponible_unidades')
    def _compute_disponible_bultos(self):
        if self.uxb:
            self.disponible_bultos = self.disponible_unidades / self.uxb
    
    
    @api.depends('comprado_unidades')
    def _compute_comprado_bultos(self):
        if self.uxb:
            self.comprado_bultos = self.comprado_unidades / self.uxb


    @api.depends('entrante_unidades')
    def _compute_entrante_bultos(self):
        if self.uxb:
            self.entrante_bultos = self.entrante_unidades / self.uxb




    ##### DEBUG METHODS #####

    def set_to_zero(self):
        self.fisico_unidades = 0