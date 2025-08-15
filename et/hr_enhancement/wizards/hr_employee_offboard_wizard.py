# wizard/hr_employee_offboard_wizard.py
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class HrEmployeeOffboardWizard(models.TransientModel):
    _name = 'hr.employee.offboard.wizard'
    _description = 'Wizard Dar de Baja Empleado'

    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True)
    date = fields.Date(string="Fecha de baja", required=True, default=fields.Date.context_today)
    reason = fields.Selection([
        ('resignation', 'Renuncia'),
        ('termination', 'Despido'),
        ('end_contract', 'Fin de contrato'),
        ('mutual', 'Acuerdo mutuo'),
        ('retirement', 'Jubilación'),
        ('other', 'Otro'),
    ], string="Motivo", required=True, default='other')
    description = fields.Text(string="Descripción / Observaciones")

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
            'company_id': emp.company_id.id or self.env.company.id,
        })

        # 2) cambiar estado del empleado a inactivo
        #    A) si tu módulo tiene un campo state ('active'/'inactive'):
        if 'state' in emp._fields:
            try:
                emp.write({'state': 'inactive'})
            except Exception:
                # B) de lo contrario, usar archivo lógico (active=False)
                emp.write({'active': False})
        else:
            emp.write({'active': False})

        # 3) log en chatter del empleado
        emp.message_post(
            body=f"Baja registrada por {self.env.user.name} el {self.date}. "
                 f"Motivo: {dict(self._fields['reason'].selection).get(self.reason)}."
        )
        return {'type': 'ir.actions.act_window_close'}
