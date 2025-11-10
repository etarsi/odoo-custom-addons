from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import date
import base64
import io
import xlsxwriter
from . import excel

class HrAttendanceCreateWizard(models.TransientModel):
    _name = 'hr.attendance.create.wizard'
    _description = 'Asistente para crear registros de asistencia'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    check_date_hour = fields.Datetime(string='Ingreso/Salida', default=fields.Datetime.now, required=True)
    justificacion = fields.Text(string='Justificación', required=True)


    def _set_justification_vals(self, vals, current_attendance=None):
        """
            Coloca la justificación en el único campo 'justification'.
            Si ya existe texto previo (en vals o en el registro actual), concatena con ' / '.
        """
        j = (self.justificacion or '').strip()
        if not j:
            return vals
        if 'justification' not in self.env['hr.attendance']._fields:
            return vals
        existing = ''
        if current_attendance:
            existing = (current_attendance.justification or '').strip()
        else:
            existing = (vals.get('justification') or '').strip()
        vals['justification'] = f"{existing} / {j}" if existing else j
        return vals 

    def action_confirm(self):
        self.ensure_one()
        #validar si esta en el grupo de RRHH
        is_allowed = (
            self.env.user.has_group('hr_enhancement.group_hr_administrador') or
            self.env.user.has_group('hr_enhancement.group_hr_supervisor')
        )
        if not is_allowed:
            # Podrías usar ValidationError, pero semánticamente AccessError calza mejor
            raise ValidationError(_("No tienes permisos para realizar esta acción."))
        emp = self.employee_id
        dt = self.check_date_hour
        attendance = self.env['hr.attendance']
        open_att = attendance.search([
            ('employee_id', '=', emp.id),
            ('check_out', '=', False),
        ], order='check_in desc', limit=1)

        if open_att:
            # Cerrar la abierta con la fecha/hora elegida
            if dt < open_att.check_in:
                raise ValidationError(_("La hora de salida (%s) no puede ser anterior a la hora de entrada abierta (%s).")
                                       % (fields.Datetime.to_string(dt), fields.Datetime.to_string(open_att.check_in)))
            write_vals = {'check_out': dt}
            write_vals = self._set_justification_vals(write_vals, current_attendance=open_att)
            open_att.write(write_vals)
            rec = open_att
        else:
            # 2) ¿Ya existe una asistencia cerrada que cubra ese instante?
            overlap = attendance.search([
                ('employee_id', '=', emp.id),
                ('check_in', '<=', dt),
                ('check_out', '>=', dt),
            ], limit=1)
            if overlap:
                raise ValidationError(_("Ya existe una asistencia registrada que cubre ese horario:\n"
                                        "Entrada: %s  -  Salida: %s")
                                      % (fields.Datetime.to_string(overlap.check_in),
                                         fields.Datetime.to_string(overlap.check_out)))
            # 3) No hay abierta -> crear ENTRADA nueva
            create_vals = {
                'employee_id': emp.id,
                'check_in': dt,
            }
            # Completar extras si existen en tu modelo
            if 'employee_type' in attendance._fields and getattr(emp, 'employee_type', False):
                create_vals['employee_type'] = emp.employee_type
            if 'employee_type_shift' in attendance._fields and hasattr(emp, 'employee_type_shift'):
                create_vals['employee_type_shift'] = getattr(emp, 'employee_type_shift')
            create_vals = self._set_justification_vals(create_vals)
            rec = attendance.create(create_vals)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'res_id': rec.id,
            'view_mode': 'tree,form',
            'name': _('Asistencia asignada'),
            'target': 'current',
        }