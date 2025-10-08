from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    _description = 'Configuracion de sistemas'

    sheet_enable= fields.Boolean(string="Habilitar Hoja", help="Habilitar la hoja de cálculo", required=True, default=False)
    sheet_spreadsheet_id = fields.Char(string="ID de Hoja de Cálculo excel", help="ID de la hoja de cálculo que se saca de la url del link del archivo compartido", required=True, default="xaxaxaxa" )
    sheet_gid = fields.Char(string="ID de Grupo de Hoja excel", help="ID del grupo de la hoja que se saca de la url del link del archivo compartido", required=True, default="123456789")

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('stock_enhancement2.sheet_enable', self.sheet_enable)
        self.env['ir.config_parameter'].sudo().set_param('stock_enhancement2.sheet_spreadsheet_id', self.sheet_spreadsheet_id)
        self.env['ir.config_parameter'].sudo().set_param('stock_enhancement2.sheet_gid', self.sheet_gid)

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update({
            'sheet_enable': bool(self.env['ir.config_parameter'].sudo().get_param('stock_enhancement2.sheet_enable', default=False)),
            'sheet_spreadsheet_id': self.env['ir.config_parameter'].sudo().get_param('stock_enhancement2.sheet_spreadsheet_id', default="xaxaxaxa"),
            'sheet_gid': self.env['ir.config_parameter'].sudo().get_param('stock_enhancement2.sheet_gid', default="123456789"),
        })
        return res