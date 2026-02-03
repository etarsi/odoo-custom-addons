# models/iva_message_wizard.py
from odoo import models, fields, _
class PopUpMessageWizard(models.TransientModel):
    _name = "pop.up.message.wizard"
    _description = "Mensaje emergente"

    message = fields.Text(readonly=True)
