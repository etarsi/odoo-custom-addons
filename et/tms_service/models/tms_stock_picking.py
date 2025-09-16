from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TmsStockPicking(models.Model):
    _name = 'tms.stock.picking'
    _description = 'Ruteo Stock Picking'

    fecha_entrega = fields.Datetime(string='Fecha de Carga')
    fecha_envio_wms = fields.Datetime(string='Fecha creacion')
    codigo_wms = fields.Char(string='Código WMS')
    sale_id = fields.Many2one('sale.order', string='Doc. Origen')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    cantidad_bultos = fields.Float(string='Cantidad de Bultos')
    cantidad_lineas = fields.Integer(string='Linea de Pedido')
    carrier_id = fields.Many2one('res.partner', string='Transportista')
    observaciones = fields.Text(string='Obs. de Operaciones')
    industry_id = fields.Many2one('res.partner.industry', string='Despacho')
    ubicacion = fields.Char(string='Ubicación')
    estado_digip = fields.Char(string='Estado Digip')
    estado_despacho = fields.Char(string='Estado Despacho')
    fecha_despacho = fields.Datetime(string='Fecha Despacho')
    observacion_despacho = fields.Text(string='Observaciones Despacho')
    contacto_calle = fields.Char(string='Contacto Calle')
    direccion_entrega = fields.Char(string='Dirección Entrega')
    contacto_cp = fields.Char(string='Contacto CP')
    contacto_ciudad = fields.Char(string='Contacto Ciudad')
    carrier_address = fields.Char(string='Transportista/Carrier Address')
    company_id = fields.Many2one('res.company', string='Compañia', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user)
    
    
    
    
    
    