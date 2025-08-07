from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    _description = 'Configuración de Horario Laboral'

    hour_start_day_check = fields.Float(string="Hora Inicio (Marcado) del Diurno", required=True, default=8.0)
    hour_end_day_check = fields.Float(string="Hora Fin (Marcado) del Diurno", required=True, default=17.0)
    hour_start_nigth_check = fields.Float(string="Hora Inicio (Marcado) del Nocturno", required=True, default=20.0)
    hour_end_nigth_check = fields.Float(string="Hora Fin (Marcado) del Nocturno", required=True, default=6.0)
    
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('hr_enhancement.hour_start_day_check', self.hour_start_day_check)
        self.env['ir.config_parameter'].sudo().set_param('hr_enhancement.hour_end_day_check', self.hour_end_day_check)
        self.env['ir.config_parameter'].sudo().set_param('hr_enhancement.hour_start_nigth_check', self.hour_start_nigth_check)
        self.env['ir.config_parameter'].sudo().set_param('hr_enhancement.hour_end_nigth_check', self.hour_end_nigth_check)
        
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update({
            'hour_start_day_check': float(self.env['ir.config_parameter'].sudo().get_param('hr_enhancement.hour_start_day_check', default=8.0)),
            'hour_end_day_check': float(self.env['ir.config_parameter'].sudo().get_param('hr_enhancement.hour_end_day_check', default=17.0)),
            'hour_start_nigth_check': float(self.env['ir.config_parameter'].sudo().get_param('hr_enhancement.hour_start_nigth_check', default=20.0)),
            'hour_end_nigth_check': float(self.env['ir.config_parameter'].sudo().get_param('hr_enhancement.hour_end_nigth_check', default=6.0)),
        })
        return res