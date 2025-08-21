from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class HrSeasonLaborCost(models.Model):
    _name = 'hr.season.labor.cost'
    _description = 'Costo Laboral por Temporada'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    _rec_name = 'name'

    name = fields.Char('Temporada', required=True, tracking=True)
    date_start = fields.Date('Inicio Temporada', required=True, tracking=True)
    date_end = fields.Date('Fin Temporada', required=True, tracking=True)

    hour_cost_normal = fields.Monetary('Costo Hora Normal', currency_field='currency_id', required=True, tracking=True)
    hour_cost_night = fields.Monetary('Costo Hora Nocturna', currency_field='currency_id', required=True, tracking=True)
    hour_cost_extra = fields.Monetary('Costo Hora Extra', currency_field='currency_id', required=True, tracking=True)
    hour_cost_holiday = fields.Monetary('Costo Hora Feriado', currency_field='currency_id', required=True, tracking=True)

    currency_id = fields.Many2one('res.currency', string="Moneda", required=True, default=lambda self: self.env.company.currency_id.id)
    user_id = fields.Many2one('res.users', string='Usuario Creador', default=lambda self: self.env.user, readonly=True, tracking=True)
    state = fields.Selection([
        ('active', 'Activo'),
        ('inactive', 'Inactivo')
    ], string="Estado", default="inactive", required=True, tracking=True)

    @api.model
    def create(self, vals):
        # Si este registro se marca como activo, desactiva los demás sin cambiar este id
        if vals.get('state', False) == 'active':
            self.search([('state', '=', 'active'), ('id', '!=', self.id)]).write({'state': 'inactive'})
        return super(HrSeasonLaborCost, self).create(vals)

    def write(self, vals):
        # Validar montos
        for field in ['hour_cost_normal', 'hour_cost_night', 'hour_cost_extra', 'hour_cost_holiday']:
            if field in vals and vals[field] <= 0:
                raise ValidationError("Los montos de Costo de Hora deben ser mayores a 0")
        if 'state' in vals and vals['state'] == 'active':
            self.search([('state', '=', 'active'), ('id', '!=', self.id)]).write({'state': 'inactive'})
        return super(HrSeasonLaborCost, self).write(vals)