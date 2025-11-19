# wizard/hr_employee_offboard_wizard.py
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class HrEmployeeOffboardWizard(models.TransientModel):
    _name = 'hr.employee.offboard.masive.wizard'
    _description = 'Wizard Bajas de Empleados'

    line_ids = fields.One2many(
        'hr.employee.offboard.masive.wizard.line',
        'wizard_id',
        string='Bajas a registrar',
    )

    def action_confirm(self):
        Offboard = self.env['hr.employee.offboard']

        for wizard in self:
            if not wizard.line_ids:
                raise ValidationError("Debe agregar al menos un empleado para dar de baja.")
            for line in wizard.line_ids:
                emp = line.employee_id
                if not emp:
                    continue

                # 1) crear el registro histórico
                Offboard.create({
                    'employee_id': emp.id,
                    'date': line.date,
                    'reason': line.reason,
                    'description': line.description,
                    'user_id': self.env.user.id,
                })

                # 2) cambiar estado del empleado a inactivo (si existe el campo state)
                if 'state' in emp._fields:
                    try:
                        emp.write({'state': 'inactive'})
                    except Exception:
                        # si por algo falla, no reviento el wizard
                        pass

                # 3) log en chatter del empleado
                motivo_label = dict(self.env['hr.employee.offboard']._fields['reason'].selection).get(line.reason, line.reason)
                emp.message_post(
                    body=(
                        f"Baja registrada por {self.env.user.name} el {line.date}."
                        f" Motivo: {motivo_label}."
                    )
                )

        return {'type': 'ir.actions.act_window_close'}


class HrEmployeeOffboardWizardLine(models.TransientModel):
    _name = 'hr.employee.offboard.masive.wizard.line'
    _description = 'Línea Wizard Baja Empleado'

    wizard_id = fields.Many2one(
        'hr.employee.offboard.masive.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string="Empleado",
        required=True,
        domain=[('active', '=', True)],
    )

    date = fields.Date(
        string="Fecha de baja",
        required=True,
        default=fields.Date.context_today,
    )

    reason = fields.Selection([
        ('resignation', 'Renuncia'),
        ('termination', 'Despido'),
        ('end_contract', 'Fin de contrato'),
        ('mutual', 'Acuerdo mutuo'),
        ('retirement', 'Jubilación'),
        ('other', 'Otro'),
    ], string="Motivo", required=True, default='other')

    description = fields.Text(string="Descripción / Observaciones")
