from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class HrSeasonLaborCost(models.Model):
    _name = 'hr.season.labor.cost'
    _description = 'Costo Laboral por Temporada'

    name = fields.Char('Temporada', required=True)
    date_start = fields.Date('Inicio Temporada', required=True)
    date_end = fields.Date('Fin Temporada', required=True)

    hour_cost_normal = fields.Float('Costo Hora Normal', required=True)
    hour_cost_night = fields.Float('Costo Hora Nocturna')
    hour_cost_extra = fields.Float('Costo Hora Extra')
    hour_cost_holiday = fields.Float('Costo Hora Feriado')

    currency_id = fields.Many2one('res.currency', string="Moneda", required=True, default=lambda self: self.env.company.currency_id.id)
    user_id = fields.Many2one('res.users', string='Usuario Creador', default=lambda self: self.env.user, readonly=True)
    active = fields.Boolean('Activo', default=True)

    @api.model
    def create(self, vals):
        # Si este registro se marca como activo, desactiva los demás
        if vals.get('active', False):
            self.search([('active', '=', True)]).write({'active': False})
        return super(HrSeasonLaborCost, self).create(vals)

    def write(self, vals):
        # Si se está activando este registro, desactiva los demás
        if 'active' in vals and vals['active']:
            self.search([('active', '=', True), ('id', '!=', self.id)]).write({'active': False})
        return super(HrSeasonLaborCost, self).write(vals)