from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TmsStockPicking(models.Model):
    _name = 'tms.stock.picking'
    _description = 'Ruteo Stock Picking'
    
    ref = fields.Char(string='Referencia')
    fecha_envio_wms = fields.Datetime(string='Fecha Envio WMS')
    codigo_wms = fields.Char(string='Codigo WMS')
    sale_id = fields.Many2one('sale.order', string='Sale Order')
    picking_id = fields.Many2one('stock.picking', string='Stock Picking')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    carrier_id = fields.Many2one('res.partner', string='Transportista')
    cantidad_bultos = fields.Float(string='Cantidad Bultos')
    cantidad_lineas = fields.Integer(string='Cantidad Lineas')
    observaciones = fields.Text(string='Observaciones')
    industry_id = fields.Many2one('res.partner.industry', string='Despacho')
    ubicacion = fields.Char(string='Ubicacion')
    estado_digip = fields.Char(string='Estado Digip')
    estado_despacho = fields.Char(string='Estado Despacho')
    fecha_despacho = fields.Datetime(string='Fecha Despacho')
    observacion_despacho = fields.Text(string='Observaciones Despacho')
    contacto_calle = fields.Char(string='Contacto Calle')
    direccion_entrega = fields.Char(string='Direccion Entrega')
    contacto_cp = fields.Char(string='Contacto CP')
    contacto_ciudad = fields.Char(string='Contacto Ciudad')
    carrier_address = fields.Char(string='Transportista/Carrier Address')
    company_id = fields.Many2one('res.company', string='Compañia', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user)
    
    
    
    
    
    