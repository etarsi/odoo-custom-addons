from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import ValidationError, UserError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    ingreso_date = fields.Date(string='Fecha de Ingreso', required=True, tracking=True)
    salida_date = fields.Date(string='Fecha de Salida', tracking=True)
    position = fields.Char(string='Puesto', required=True, tracking=True)
    dni = fields.Char(string='DNI', required=True, tracking=True)
    dni_photo_front = fields.Binary('Foto DNI frontal', tracking=True)
    dni_photo_back = fields.Binary('Foto DNI Reverso', tracking=True)
    cuil = fields.Char(string='CUIL', required=True, tracking=True)
    celular = fields.Char(string='Celular', required=True, tracking=True)
    email_personal = fields.Char(string='Email', required=True, 
                         help='Email personal del empleado, no se usa para notificaciones.', tracking=True)

    #datos familiares
    spouse_dni = fields.Char(string='DNI del Cónyuge', tracking=True)
    is_children = fields.Boolean(string='Tiene Hijos', default=False, tracking=True)

    #relación de uno a muchos para los hijos
    children_ids = fields.One2many('hr.employee.children', 'employee_id', string='Hijos', tracking=True)
    #familiar a cargo
    dependent_name = fields.Char(string='Nombre del Familiar a Cargo', tracking=True)
    dependent_dni = fields.Char(string='DNI del Familiar a Cargo', tracking=True)

    #datos de cuenta bancaria
    bank = fields.Char(string='Banco', required=True, tracking=True)
    nro_account = fields.Char(string='Número de Cuenta', required=True, tracking=True)
    cbu = fields.Char(string='CBU', required=True, tracking=True)
    alias = fields.Char(string='Alias', required=True, tracking=True)

    #que monto de sueldo sea una relación de uno a muchos
    salary_ids = fields.One2many('hr.employee.salary', 'employee_id', string='Sueldos')
    wage = fields.Float(string="Sueldo Actual", tracking=True)
    total_percentage_increase = fields.Float(
        string="Porcentaje Total de Incremento",
        compute='_compute_total_percentage_increase'
    )
    alta_afip = fields.Date('Fecha de Alta AFIP', tracking=True)
    
    #firma del empleado digital
    digital_signature = fields.Binary('Firma Digital (PNG)', tracking=True)
    digital_signature_name = fields.Char('Nombre de la Firma Digital')
    
    #licencias asignadas
    license_ids = fields.One2many('hr.license', 'employee_id', string='Licencias Asignadas')
    #contador de licencias asignadas
    license_count = fields.Integer(string='Cantidad de Licencias Asignadas', compute='_compute_license_count', store=True)
    #direccion asignada
    location_id = fields.Many2one('hr.location', string='Ubicación Actual', ondelete='set null', tracking=True)
    #listado de solicitudes de edicion
    edit_request_ids = fields.One2many(
        'hr.employee.edit.request',
        'employee_id',
        string="Solicitudes de Edición"
    )
    
    #estado del emple
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
    ], string='Estado', default='draft', tracking=True)
    
    employee_type = fields.Selection(
        selection_add=[('eventual', 'Eventuales')],
        ondelete={'eventual': 'set default'},
        default='employee', tracking=True
    )

    _sql_constraints = [
        ('unique_dni', 'UNIQUE(dni)', 'El DNI debe ser único por empleado.'),
        ('unique_cuil', 'UNIQUE(cuil)', 'El CUIL debe ser único por empleado.'),
        ('unique_celular', 'UNIQUE(celular)', 'El Celular debe ser único por empleado.'),
        ('unique_cbu', 'UNIQUE(cbu)', 'El CBU debe ser único por empleado.'),
        ('unique_alias', 'UNIQUE(alias)', 'El Alias debe ser único por empleado.'),
        ('unique_account', 'UNIQUE(nro_account)', 'El Número de Cuenta debe ser único por empleado.'),
    ]

    @api.depends('salary_ids.percentage_increase')
    def _compute_total_percentage_increase(self):
        for rec in self:
            rec.total_percentage_increase = sum(rec.salary_ids.mapped('percentage_increase'))

    @api.depends('license_ids')
    def _compute_license_count(self):
        for employee in self:
            employee.license_count = len(employee.license_ids)

    @api.model
    def action_open_my_profile(self):
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if employee:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Mi Perfil',
                'res_model': 'hr.employee',
                'view_mode': 'form',
                'res_id': employee.id,
                'target': 'current',
            }
        else:
            return {'type': 'ir.actions.act_window_close'}


    @api.constrains('digital_signature', 'digital_signature_filename')
    def _check_signature_is_png(self):
        for rec in self:
            if rec.digital_signature and rec.digital_signature_name:
                if not rec.digital_signature_name.lower().endswith('.png'):
                    raise ValidationError("La firma digital debe ser un archivo PNG (.png).")
                
    def action_request_edit(self, *args, **kwargs):
        for rec in self:
            rec.env['hr.employee.edit.request'].create({
                'employee_id': rec.id,
                'user_id': rec.user_id.id,
                'request_date': datetime.now(),
                'reason': 'Editar Información del empleado',
            })
            rec.env.user.notify_info("¡Solicitud de Modificar Empleado enviada con éxito!")

    def action_confirm(self, *args, **kwargs):
        for record in self:
            record.state = 'confirmed'
            
    def action_view_my_licenses(self):
        # Obtén las licencias asociadas a este empleado
        action = self.env.ref('hr_enhancement.action_my_licenses')  # Ajusta el ID de la acción si es necesario
        result = action.read()[0]
        
        # Filtrar para que solo se vean las licencias del empleado actual
        result['domain'] = [('employee_id.user_id', '=', self.env.user.id)]

        # Asegurar que la vista por defecto sea la vista tree
        result['view_mode'] = 'tree'
        return result
    
    @api.ondelete(at_uninstall=False)
    def _check_employee_records(self):
        """
            Verifica si el empleado tiene licencias asociadas antes de eliminar
        """
        for employee in self:
            license_count = self.env['hr.license'].search_count([
                ('employee_id', '=', employee.id)
            ])
            if license_count > 0:
                raise ValidationError((
                    "No se puede eliminar el empleado %s porque tiene %d licencias asociadas. "
                    "Por favor, elimine primero las licencias antes de continuar."
                ) % (employee.name, license_count))

    def unlink(self):
        """
            Sobreescribe el método unlink para validar licencias antes de eliminar
        """
        self._check_employee_records()
        return super(HrEmployee, self).unlink()