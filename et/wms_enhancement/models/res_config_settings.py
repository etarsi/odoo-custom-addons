from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    _description = 'Configuracion de sistemas'

    wms_sheet_enable= fields.Boolean(string="Habilitar Hoja", help="Habilitar la hoja de cálculo", required=True, default=False)
    wms_sheet_spreadsheet_id = fields.Char(string="ID de Hoja de Cálculo excel", help="ID de la hoja de cálculo que se saca de la url del link del archivo compartido", required=True, default="xaxaxaxa" )
    wms_sheet_gid = fields.Char(string="ID de Grupo de Hoja excel", help="ID del grupo de la hoja que se saca de la url del link del archivo compartido", required=True, default="123456789")

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('wms_enhancement.wms_sheet_enable', self.wms_sheet_enable)
        self.env['ir.config_parameter'].sudo().set_param('wms_enhancement.wms_sheet_spreadsheet_id', self.wms_sheet_spreadsheet_id)
        self.env['ir.config_parameter'].sudo().set_param('wms_enhancement.wms_sheet_gid', self.wms_sheet_gid)

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update({
            'wms_sheet_enable': bool(self.env['ir.config_parameter'].sudo().get_param('wms_enhancement.wms_sheet_enable', default=False)),
            'wms_sheet_spreadsheet_id': self.env['ir.config_parameter'].sudo().get_param('wms_enhancement.wms_sheet_spreadsheet_id', default="xaxaxaxa"),
            'wms_sheet_gid': self.env['ir.config_parameter'].sudo().get_param('wms_enhancement.wms_sheet_gid', default="123456789"),
        })
        return res