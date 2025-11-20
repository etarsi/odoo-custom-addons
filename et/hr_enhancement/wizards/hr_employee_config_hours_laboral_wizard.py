# wizard/hr_employee_offboard_wizard.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrEmployeeConfigHoursLaboralWizard(models.TransientModel):
    _name = 'hr.employee.config.hours.laboral.wizard'
    _description = 'Wizard Configurar Horas Laborales Empleado'

    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True)
    dni = fields.Char(string="DNI", required=True)
    hr_works_schedule_id = fields.Many2one(
        string='Horario de Trabajo',
        comodel_name='hr.works.schedule',
        ondelete='restrict',
    )
    type_shift = fields.Selection(relatted='employee_id.type_shift', string="Tipo de Turno")
    id_lector = fields.Char(string="ID Lector")
    employee_type = fields.Selection(related='employee_id.employee_type', string="Tipo de Empleado")
    
    def action_confirm(self):
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            raise ValidationError("No se encontró el empleado seleccionado.")
        emp.write({
            'dni': self.dni,
            'hr_works_schedule_id': self.hr_works_schedule_id.id,
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

