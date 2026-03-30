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

class StockERPGC(models.Model):
    _name = 'stock.erp.gc'
    _description = 'Stock ERP GC'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(compute='_compute_name')
    move_lines = fields.One2many('stock.moves.erp.gc', 'stock_erp_gc')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    product_code = fields.Char(string="Código", compute="_compute_product_info", store=True)
    product_name = fields.Char(string='Producto', compute="_compute_product_info", store=True)
    product_brand_id = fields.Many2one('product.brand', string='Marca', related='product_id.product_brand_id', store=True)
    product_category = fields.Many2one('product.category', string="Categoría", compute="_compute_category_id", store=True)
    uxb = fields.Integer('UxB', default=0)

    fisico_unidades = fields.Integer('Físico Unidades')
    enelagua_unidades = fields.Integer('En el Agua Unidades')
    total_unidades = fields.Integer('Total Unidades', compute="_compute_total", store=True)
    comprometido_unidades = fields.Integer('Comprometido Unidades', store=True)
    disponible_unidades = fields.Float('Disponible Unidades', digits=(99,0), compute="_compute_disponible_unidades", store=True)
    entregable_unidades = fields.Integer('Entregable Unidades')
    

    fisico_bultos = fields.Float('Físico Bultos', compute="_compute_fisico_bultos", store=True)
    enelagua_bultos = fields.Float('En el Agua Bultos', compute="_compute_enelagua_bultos", store=True)    
    total_bultos = fields.Float('Total Bultos', compute="_compute_total", store=True)
    comprometido_bultos = fields.Float('Comprometido Bultos', compute="_compute_comprometido_bultos", store=True)
    disponible_bultos = fields.Float('Disponible Bultos', compute="_compute_disponible_bultos", store=True)
    entregable_bultos = fields.Float('Entregable Bultos', compute="_compute_entregable_bultos", store=True)
    
    digip_unidades = fields.Integer('Digip Unidades')

    pdl = fields.Float(string="Precio de Lista")
    valor = fields.Float(string="Valor")

    def calculate_stock_value(self):
        for record in self:
            if record.fisico_unidades > 0:
                pricelist = self.env['product.pricelist.item'].search([('pricelist_id', '=', 45), ('product_tmpl_id','=', record.product_id.product_tmpl_id.id)], limit=1)
                
                if pricelist:
                    record.pdl = pricelist.fixed_price

                record.valor = record.pdl * record.fisico_unidades

    def update_cantidad_entregada_line(self):
        for record in self:
            if record.move_lines_reserved:
                for line in record.move_lines_reserved:
                    lineas_entregadas = self.env['stock.moves.erp'].search([
                        ('sale_line_id', '=', line.sale_line_id.id),
                        ('type', '=', 'delivery')])
                    if lineas_entregadas:
                        total_entregado = sum(lineas_entregadas.mapped('quantity'))
                        line.write({'quantity_delivered': total_entregado})
                    else:
                        line.write({'quantity_delivered': 0})
    
    def _action_update_cantidad_entregada_line(self):
        self.update_cantidad_entregada_line()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Listo',
                'message': 'Se recalcularon las entregas (reserve/preparation) desde las deliveries.',
                'type': 'success',
                'sticky': False,
            }
        }

    def update_comprometido_line(self):
        for record in self:
            if record.move_lines_reserved:
                for line in record.move_lines_reserved:
                    if line.sale_line_id.product_uom_qty != line.quantity:
                        line.write({'quantity': line.sale_line_id.product_uom_qty})
    
    def _action_update_comprometido_line(self):
        self.update_comprometido_line()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Listo',
                'message': 'Se actualizaron las líneas comprometidas desde las órdenes de venta.',
                'type': 'success',
                'sticky': False,
            }
        }

    def update_digip_stock(self):

        stock_digip = self.get_digip_stock()        
        
        for record in stock_digip:
            stock_erp = self.env['stock.erp'].search([('product_id.default_code', '=', record['codigo'])], limit=1)
            if stock_erp:
                stock_digip = record['stock']['disponible'] + record['stock']['enPreparacion'] + record['stock']['bloqueados'] 
                stock_erp.digip_unidades = stock_digip
                stock_erp.fisico_unidades = stock_digip
                stock_erp.entregable_unidades = record['stock']['disponible']

    def action_update_comprometido_unidades(self):
        self.ensure_one()
        self.update_comprometido_unidades_stock()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Listo',
                'message': 'Se actualizaron las unidades comprometidas de los productos.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def update_comprometido_unidades_stock(self):
        stocks_erp = self.env['stock.erp'].search([])
        for stock_erp in stocks_erp:
            lines = stock_erp.move_lines_reserved.filtered(lambda l: l.sale_line_id)
            comprometido_unidades = sum(lines.mapped('quantity')) if lines else 0.0
            stock_erp.write({'comprometido_unidades': comprometido_unidades})

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


    def increase_enelagua_unidades(self, quantity):
        for record in self:
            record.enelagua_unidades += quantity
    
    
    def increase_comprometido_unidades(self, quantity):
        for record in self:
            record.comprometido_unidades += quantity


    def increase_entregable_unidades(self, quantity):
        for record in self:
            record.entregable_unidades += quantity


    def decrease_fisico_unidades(self, quantity):
        for record in self:
            if quantity <= record.fisico_unidades:
                record.fisico_unidades -= quantity
            else: 
                raise UserError(f'Para el producto: [{record.product_id.default_code}] {record.product_id.name}, tiene {record.fisico_unidades} unidades y quiere entregar {quantity} unidades. El resultado no puede ser negativo')
            
            
    def decrease_comprometido_unidades(self, quantity):
        for record in self:
            if quantity <= record.comprometido_unidades:
                record.comprometido_unidades -= quantity
            else:
                record.comprometido_unidades = 0 
                # raise UserError(f'Para el producto: [{record.product_id.default_code}] {record.product_id.name}, tiene {record.comprometido_unidades} unidades comprometidas y quiere liberar {quantity} unidades. El resultado no puede ser negativo')


    def decrease_entregable_unidades(self, quantity):
        for record in self:
            if quantity <= record.entregable_unidades:
                record.entregable_unidades -= quantity
            else: 
                raise UserError(f'Para el producto: [{record.product_id.default_code}] {record.product_id.name}, tiene {record.entregable_unidades} unidades entregable y quiere preparar {quantity} unidades. El resultado no puede ser negativo')


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
    def _compute_move_lines_prepared(self):
        for record in self:
            record.move_lines_prepared = record.move_lines.filtered(
                lambda l: l.type == 'preparation')
            
    
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

    
    @api.depends('entregable_unidades')
    def _compute_entregable_bultos(self):
        for record in self:
            if record.uxb:
                record.entregable_bultos = record.entregable_unidades / record.uxb
            else: record.entregable_bultos = 0


    @api.depends('entrante_unidades')
    def _compute_entrante_bultos(self):
        for record in self:
            if record.uxb:
                record.entrante_bultos = record.entrante_unidades / record.uxb
            else: record.entrante_bultos = 0


    ##### DEBUG METHODS #####

    def set_to_zero(self):
        self.fisico_unidades = 0


    @api.depends('disponible_unidades', 'stock_limit_unidades')
    def _compute_below_limit(self):
        for rec in self:
            limit_val = rec.stock_limit_unidades or 0
            rec.below_limit = bool(limit_val > 0 and (rec.disponible_unidades or 0) < limit_val)
            rec.alert_sent = rec.alert_sent if rec.below_limit else False  # resetea alerta si ya no está bajo límite

    def _get_alert_users(self):
        """Usuarios a notificar."""
        self.ensure_one()
        group = self.env.ref('stock_erp.group_alert_stock', raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        return group.users.filtered(lambda u: u.active)

    def _build_alert_email_to(self, users):
        """Arma email_to con los emails de los usuarios del grupo."""
        emails = []
        for u in users:
            if u.login and '@' in u.login:
                emails.append(u.login.strip())
        # dedupe manteniendo orden
        seen = set()
        uniq = []
        for e in emails:
            if e and e not in seen:
                uniq.append(e)
                seen.add(e)
        return ",".join(uniq)

    


class StockMovesERPGC(models.Model):
    _name = 'stock.moves.erp.gc'


    