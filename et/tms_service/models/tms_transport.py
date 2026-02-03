from odoo import models, fields, api

class TmsTransport(models.Model):
    _name = 'tms.transport'
    _description = 'Transporte'

    name = fields.Char(string='Descripción', required=True)
    patente_trc = fields.Char(string='Patente Tractor', required=True)
    patente_semi = fields.Char(string='Patente Semi', required=True)
    active = fields.Boolean(string='Activo', default=True)
    transport_type_id = fields.Many2one('tms.transport.type', string='Tipo de Transporte')
    delivery_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Empresa de Transporte',
        required=True,
        ondelete='restrict',
        index=True,
    )

    
class TmsTransportType(models.Model):
    _name = 'tms.transport.type'
    _description = 'Tipo de Transporte'

    name = fields.Char(string='Descripción', required=True)
    code = fields.Char(string='Código', required=True)
    active = fields.Boolean(string='Activo', default=True)



class TmsService(models.Model):
    _name = 'tms.service'
    _description = 'Servicio de Transporte'

    name = fields.Char(string='Descripción', required=True)
    code = fields.Char(string='Código', required=True)
    active = fields.Boolean(string='Activo', default=True)
    

class TmsHiring(models.Model):
    _name = 'tms.hiring'
    _description = 'Contratación de Transporte'

    name = fields.Char(string='Referencia', required=True)
    date_hired = fields.Datetime(string='Fecha de Contratación', default=fields.Datetime.now, required=True)
    transport_id = fields.Many2one('tms.transport', string='Transporte Contratado', required=True)
    service_id = fields.Many2one('tms.service', string='Servicio Contratado', required=True)
    observations = fields.Text(string='Observaciones')