# wizard/hr_employee_offboard_wizard.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrEmployeeConfigHoursLaboralWizard(models.TransientModel):
    _name = 'hr.employee.config.hours.laboral.wizard'
    _description = 'Wizard Configurar Horas Laborales Empleado'

    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True)
    dni = fields.Char(string="DNI", required=True)
    work_schedule_id = fields.Many2one(
        string='Horario de Trabajo',
        comodel_name='hr.work.schedule',
        ondelete='restrict',
    )
    id_lector = fields.Char(string="ID Lector")
    employee_type = fields.Selection(
        string='Tipo de Empleado',
        selection=[('eventual', 'Eventual'),
                   ('employee', 'Empleado')],
        default='employee')
    type_shift = fields.Selection([
        ('day', 'Turno Día'),
        ('night', 'Turno Noche'),
    ], string='Tipo de Turno', default='day', tracking=True)
    
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        emp = self.env['hr.employee'].browse(self._context.get('active_id'))
        if emp:
            res.update({
                'employee_id': emp.id,
                'dni': emp.dni,
                'work_schedule_id': emp.work_schedule_id.id,
                'type_shift': emp.type_shift,
                'id_lector': emp.id_lector,
                'employee_type': emp.employee_type,
            })
        return res
    
    def action_confirm(self):
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            raise ValidationError("No se encontró el empleado seleccionado.")
        emp.write({
            'dni': self.dni,
            'work_schedule_id': self.work_schedule_id.id,
            'type_shift': self.type_shift,
            'id_lector': self.id_lector,
            'employee_type': self.employee_type,
        })
        # Empleado Actualizado correctamente
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Empleado Actualizado'),
                'message': _('El empleado fue actualizado correctamente.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

