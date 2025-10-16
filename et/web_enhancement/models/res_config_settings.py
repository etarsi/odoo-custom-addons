from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    _description = 'Configuracion de sistemas'

    sheet_drive_folder_path = fields.Char(string="ID de Carpeta en Drive", help="ID de la carpeta en Drive Padre de las imagenes", required=True, default="123456789")
    shop_gate_password = fields.Char(string="Contraseña de acceso a la tienda", help="Contraseña para acceder a la tienda", required=True, default="odoo2024")

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('web_enhancement.sheet_drive_folder_path', self.sheet_drive_folder_path)
        self.env['ir.config_parameter'].sudo().set_param('web_enhancement.shop_gate_password', self.shop_gate_password)

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update({
            'sheet_drive_folder_path': self.env['ir.config_parameter'].sudo().get_param('web_enhancement.sheet_drive_folder_path', default="123456789"),
            'shop_gate_password': self.env['ir.config_parameter'].sudo().get_param('web_enhancement.shop_gate_password', default="odoo2024"),
        })
        return res