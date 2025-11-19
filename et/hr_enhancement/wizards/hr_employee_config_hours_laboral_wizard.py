# wizard/hr_employee_offboard_wizard.py
from odoo import api, fields, models
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

        # 1) crear el registro histórico
        self.env['hr.employee.offboard'].create({
            'employee_id': emp.id,
            'date': self.date,
            'reason': self.reason,
            'description': self.description,
            'user_id': self.env.user.id,
        })

        # 2) cambiar estado del empleado a inactivo
        if 'state' in emp._fields:
            try:
                emp.write({'state': 'inactive'})
            except Exception:
                emp.write({'state': 'active'})
        else:
            emp.write({'state': 'inactive'})

        # 3) log en chatter del empleado
        emp.message_post(
            body=f"Baja registrada por {self.env.user.name} el {self.date}. "
                 f"Motivo: {dict(self._fields['reason'].selection).get(self.reason)}."
        )
        return {'type': 'ir.actions.act_window_close'}
