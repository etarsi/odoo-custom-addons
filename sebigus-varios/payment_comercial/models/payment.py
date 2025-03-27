from odoo import tools, models, fields, api, _
import base64
import logging
_logger = logging.getLogger(__name__)

class PaymentComercial(models.Model):
    _inherit = "account.payment.group"
    comercial_id = fields.Many2one("res.users", string="Comercial",related='partner_id.user_id',readonly=True)

class PaymentComercialP(models.Model):
    _inherit = "account.payment"
    comercial_id = fields.Many2one("res.users", string="Comercial",related='partner_id.user_id',readonly=True)
