from odoo import models, fields, api



class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    tms_transport_ids = fields.One2many(
        'tms.transport',
        'delivery_carrier_id',
        string='Transportes Asociados',
        help='Transportes asociados a esta empresa de transporte.'
    )