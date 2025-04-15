from odoo import models, fields

class RemitoTest(models.Model):
    _name = 'remito.test'
    _description = 'Test de apertura de múltiples remitos'

    name = fields.Char(string="Nombre", required=True, default="Remito de prueba")

    def action_abrir_remitos(self):
        urls = [
            "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            "https://www.orimi.com/pdf-test.pdf"
        ]
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_and_open_remitos',
            'params': {
                'urls': urls,
            }
        }