from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrHolidayCustom(models.Model):
    _name = 'hr.holiday.custom'
    _description = 'Feriados y Días No Laborables'

    name = fields.Char(string="Nombre del feriado", required=True)
    date = fields.Date(string="Fecha", required=True)
    description = fields.Text(string="Descripción / Motivo")
    is_public_holiday = fields.Boolean(string="Es feriado oficial", default=True)

    @api.constrains('date')
    def _check_unique_date(self):
        for record in self:
            if self.search_count([('date', '=', record.date), ('id', '!=', record.id)]) > 0:
                raise ValidationError("Ya existe un feriado registrado para la fecha: %s" % record.date)