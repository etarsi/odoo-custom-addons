from odoo import models, fields, api



class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    transport_type_id = fields.Many2one('tms.transport.type', string="Tipo de Vehículo")
    patent_tractor = fields.Char(string="Patente Tractor")
    patent_semi = fields.Char(string="Patente Semi")