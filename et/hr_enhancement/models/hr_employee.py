from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    ingreso_date = fields.Date(string='Fecha de Ingreso', required=True)
    salida_date = fields.Date(string='Fecha de Salida')
    position = fields.Char(string='Puesto', required=True)
    dni = fields.Char(string='DNI', required=True)
    dni_foto_front = fields.Binary('Foto DNI')
    dni_foto_back = fields.Binary('Foto DNI 2')
    cuil = fields.Char(string='CUIL', required=True)
    celular = fields.Char(string='Celular', required=True)
    email_personal = fields.Char(string='Email', required=True, 
                         help='Email personal del empleado, no se usa para notificaciones.')
    
    #datos familiares
    spouse_dni = fields.Char(string='DNI del Cónyuge')
    is_children = fields.Boolean(string='Tiene Hijos', default=False)
    #relación de uno a muchos para los hijos
    children_ids = fields.One2many('hr.employee.children', 'employee_id', string='Hijos')
    #familiar a cargo
    dependent_name = fields.Char(string='Nombre del Familiar a Cargo')
    dependent_dni = fields.Char(string='DNI del Familiar a Cargo')

    #datos de cuenta bancaria
    bank = fields.Char(string='Banco', required=True)
    nro_account = fields.Char(string='Número de Cuenta', required=True)
    cbu = fields.Char(string='CBU', required=True)
    alias = fields.Char(string='Alias', required=True)

    #que monto de sueldo sea una relación de uno a muchos
    salary_ids = fields.One2many('hr.employee.salary', 'employee_id', string='Sueldos')
    alta_afip = fields.Date('Fecha de Alta AFIP')
    
    #firma del empleado digital
    digital_signature = fields.Binary('Firma Digital (PNG)')
    digital_signature_name = fields.Char('Nombre de la Firma Digital')
    
    #licencias asignadas
    license_ids = fields.One2many('hr.license', 'employee_id', string='Licencias Asignadas')
    #contador de licencias asignadas
    license_count = fields.Integer(string='Cantidad de Licencias Asignadas', compute='_compute_license_count', store=True)
    #direccion asignada
    location_id = fields.Many2one('hr.location', string='Ubicación Actual', ondelete='set null')
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
    ], string='Estado', default='draft')

    _sql_constraints = [
        ('unique_dni', 'UNIQUE(dni)', 'El DNI debe ser único por empleado.'),
        ('unique_cuil', 'UNIQUE(cuil)', 'El CUIL debe ser único por empleado.'),
        ('unique_celular', 'UNIQUE(celular)', 'El Celular debe ser único por empleado.'),
        ('unique_cbu', 'UNIQUE(cbu)', 'El CBU debe ser único por empleado.'),
        ('unique_alias', 'UNIQUE(alias)', 'El Alias debe ser único por empleado.'),
        ('unique_account', 'UNIQUE(nro_account)', 'El Número de Cuenta debe ser único por empleado.'),
    ]
    
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
            self.env['hr.employee.edit.request'].create({
                'employee_id': rec.id,
                'reason': 'Editar Información del empleado',
            })
        return True
            # Notificar por Odoo/mail al encargado de RRHH
            #"""             group_hr_manager = self.env.ref('hr.group_hr_manager')
            #users = group_hr_manager.users
            #rec.message_post(
            #    subject="Solicitud de edición de datos",
            #    body=f"El empleado {rec.name} solicitó editar su información.<br>Motivo: {reason}",
            #    partner_ids=[(4, user.partner_id.id) for user in users]
            #) """
            # Opcional: Notificar por email
            # self.env['mail.mail'].create({...})

    def action_confirm(self, *args, **kwargs):
        for record in self:
            record.state = 'confirmed'
            
    def action_view_my_licenses(self):
        # Obtén las licencias asociadas a este empleado
        action = self.env.ref('hr_enhancement.action_my_licenses')  # Ajusta el ID de la acción si es necesario
        result = action.read()[0]
        
        # Filtrar para que solo se vean las licencias del empleado actual
        result['domain'] = [('employee_id', '=', self.id)]
        
        # Asegurar que la vista por defecto sea la vista tree
        result['view_mode'] = 'tree'
        return result