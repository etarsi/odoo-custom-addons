from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class HrLocation(models.Model):
    _name = 'hr.location'
    _description = 'Ubicación del Empleado'

    street = fields.Char(string='Calle', required=True)
    street2 = fields.Char(string='Calle 2')
    city = fields.Char(string='Ciudad', required=True)
    floor = fields.Char(string='Piso')
    cp_code = fields.Char(string='Código Postal', required=True)
    country_id = fields.Many2one('res.country', string='País', required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    latitude = fields.Float(string='Latitud')
    longitude = fields.Float(string='Longitud')
    state = fields.Selection(
        [('draft', 'Borrador'), ('confirmed', 'Confirmado'), ('done', 'Hecho')],
        string='Estado', default='draft', required=True
    )
    document = fields.Binary(string='Documento de Ubicación')
    document_name = fields.Char(string='Nombre del Documento')

    @api.constrains('document', 'document_name')
    def _check_document(self):
        for record in self:
            if not record.document:
                raise ValidationError(_('El documento es obligatorio.'))
            if not record.document_name:
                raise ValidationError(_('El nombre del documento es obligatorio.'))
            if not record.document_name.lower().endswith(('.pdf')):
                raise ValidationError('Solo se pueden subir archivos PDF.')
