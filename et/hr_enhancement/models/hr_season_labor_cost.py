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
    active = fields.Boolean('Activo', default=True, tracking=True)
    
    def _check_no_overlap(self, vals, exclude_id=None):
        """Valida que no haya solapamiento de fechas con otros registros activos."""
        date_start = vals.get('date_start', self.date_start)
        date_end = vals.get('date_end', self.date_end)
        domain = [
            ('date_start', '<=', date_end),
            ('date_end', '>=', date_start)
        ]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        if self.search_count(domain):
            raise ValidationError(
                "Ya existe una temporada registrada que se superpone con el rango de fechas seleccionado."
            )

    @api.model
    def create(self, vals):
        # Validar solapamiento antes de crear
        self._check_no_overlap(vals)
        # Si este registro se marca como activo, desactiva los demás
        if vals.get('active', False):
            self.search([('active', '=', True)]).write({'active': False})
        return super(HrSeasonLaborCost, self).create(vals)

    def write(self, vals):
        # Validar solapamiento antes de escribir
        self._check_no_overlap(vals, exclude_id=self.id)
        # Validar montos
        for field in ['hour_cost_normal', 'hour_cost_night', 'hour_cost_extra', 'hour_cost_holiday']:
            if field in vals and vals[field] <= 0:
                raise ValidationError("Los montos de Costo de Hora deben ser mayores a 0")
        if 'active' in vals and vals['active']:
            self.search([('active', '=', True), ('id', '!=', self.id)]).write({'active': False})
        return super(HrSeasonLaborCost, self).write(vals)