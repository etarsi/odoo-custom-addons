from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date

class HrPayrollSalary(models.Model):
    _name = 'hr.payroll.salary'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Planilla de Sueldo de Empleados'

    name = fields.Char(string="Nombre de la Planilla", required=True, tracking=True)
    date_start = fields.Date(string="Fecha Inicio", required=True, default=fields.Date.today, tracking=True)
    date_end = fields.Date(string="Fecha Fin", required=True, default=fields.Date.today, tracking=True)
    #colocar el tipo de pago
    type_paid = fields.Selection([
        ('semanal', 'Semanal'),
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
        ('dia', 'Día'),
        ('otro', 'Otro')
    ], string="Tipo de Pago", default='quincenal', required=True, tracking=True)
    pay_month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'), ('5', 'Mayo'), ('6', 'Junio'),
        ('7', 'Julio'), ('8', 'Agosto'), ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ], string='Mes', default=lambda self: str(date.today().month), tracking=True)
    pay_year = fields.Integer(string='Año', tracking=True, default=lambda self: date.today().year)
    #que mas deberia polocar en un payroll
    state = fields.Selection([('draft', 'Borrador'),
                               ('confirmed', 'Confirmado'),
                               ('paid', 'Pagado'),
                               ('cancelled', 'Cancelado')],
                              string='Estado', default='draft', tracking=True)
    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id.id
    )
    employee_type = fields.Selection([
        ('employee', 'Fijo'),
        ('eventual', 'Eventual'),
    ], string="Tipo de Empleado a Pagar", default='eventual', required=True, tracking=True)
    #totales de la planilla
    total_amount = fields.Monetary(
        string="Total a Pagar",
        compute='_compute_total_amount',
        currency_field='currency_id',
        store=True
    )
    line_ids = fields.One2many('hr.payroll.salary.line', 'payroll_id', string="Detalles de Planilla", copy=True)
    
    
    @api.model
    def create(self, vals):
        # Si viene default desde el action, respetalo
        if 'employee_type' not in vals and self.env.context.get('default_employee_type'):
            vals['employee_type'] = self.env.context['default_employee_type']
        rec = super().create(vals)
        return rec

    def write(self, vals):
        # No permitir cambiar employee_type una vez creado
        if 'employee_type' in vals:
            for r in self:
                if r.employee_type and vals['employee_type'] != r.employee_type:
                    raise ValidationError("El tipo de empleado no puede modificarse en la planilla.")
        return super().write(vals)

    @api.depends('line_ids.net_amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('net_amount'))
            
    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError('Solo se puede confirmar una planilla en estado Borrador.')
            record.state = 'confirmed'
            # Aquí podrías agregar lógica adicional para procesar la planilla, como enviar notificaciones o generar informes.
            
    def action_cancelled(self):
        for record in self:
            if record.state not in ['draft', 'confirmed']:
                raise ValidationError('Solo se puede cancelar una planilla en estado Borrador o Confirmado.')
            record.state = 'cancelled'
            # Aquí podrías agregar lógica adicional para manejar la cancelación, como revertir pagos o notificar a los empleados.

    def action_paid(self):
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError('Solo se puede marcar una planilla como Pagada en estado Confirmado.')
            record.state = 'paid'
            # Aquí podrías agregar lógica adicional para procesar el pago, como registrar transacciones contables o enviar notificaciones a los empleados.

    def action_draft(self):
        for record in self:
            if record.state not in ['confirmed']:
                raise ValidationError('Solo se puede restablecer a Borrador una planilla en estado Confirmado.')
            record.state = 'draft'
            
    def action_load_employees(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError('Solo se pueden cargar empleados en una planilla en estado Borrador.')
            # no eliminar las lineas de la planilla sino traer los empleados que falten
            if record.line_ids:
                existing_employees = record.line_ids.mapped('employee_id')
                employees = self.env['hr.employee'].search([('employee_type', '=', record.employee_type), ('id', 'not in', existing_employees.ids)])
            else:
                employees = self.env['hr.employee'].search([('employee_type', '=', record.employee_type)])
            for emp in employees:
                attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', emp.id),
                    ('check_in', '>=', record.date_start),
                    ('check_in', '<=', record.date_end),
                ])
                if attendances:
                    total_hours = sum(a.worked_hours for a in attendances)
                    total_overtime = sum(a.overtime for a in attendances)
                    total_holiday_hours = sum(a.holiday_hours for a in attendances)
                    self.env['hr.payroll.salary.line'].create({
                        'payroll_id': record.id,
                        'employee_id': emp.id,
                        'basic_amount': emp.wage,
                        'worked_hours': total_hours,
                        'overtime': total_overtime,
                        'holiday_hours': total_holiday_hours,
                    })

    
class HrPayrollSalaryLine(models.Model):
    _name = 'hr.payroll.salary.line'
    _description = 'Detalle de Planilla de Pago' 
    _inherit = ['mail.thread', 'mail.activity.mixin']

    payroll_id = fields.Many2one('hr.payroll.salary', string="Planilla", required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True)
    employee_state = fields.Selection(
        related='employee_id.state', string='Estado Empleado', store=False, readonly=True
    )
    job_id = fields.Many2one(related='employee_id.job_id', string="Puesto", store=True)
    worked_days = fields.Float('Días Trabajados', compute='_compute_attendance',  readonly=True, store=True)
    worked_hours = fields.Float('H. Trabajadas', compute='_compute_attendance', readonly=True, store=True)
    overtime = fields.Float('H. 50%', compute='_compute_attendance', readonly=True, store=True)
    holiday_hours = fields.Float('H. 100%', compute='_compute_attendance', readonly=True, store=True)
    salary_id = fields.Many2one('hr.employee.salary', string="Sueldo Básico", help="Sueldo básico por el período")
    basic_amount = fields.Monetary('Sueldo Básico', help="Sueldo básico")
    bonus = fields.Monetary('Bonos/Gratificación', currency_field='currency_id', default=0.0)
    discount = fields.Monetary('Descuento', currency_field='currency_id', default=0.0)
    holidays = fields.Monetary('Días de Licencia', currency_field='currency_id', default=0.0)
    gross_amount = fields.Monetary('Monto Neto', currency_field='currency_id', compute='_compute_amount', store=True)
    net_amount = fields.Monetary('Total a Cobrar', currency_field='currency_id', compute='_compute_amount', readonly=True, store=True)
    note = fields.Char('Nota (Observaciones)')
    currency_id = fields.Many2one(
    'res.currency',
    string="Moneda",
    required=True,
    default=lambda self: self.env.company.currency_id.id
    )
    state = fields.Selection(related='payroll_id.state', string='Estado', store=True)
    labor_cost_id = fields.Many2one('hr.season.labor.cost', string="Costo Laboral")
    #campo para saber que si fue pagado para eventuales
    is_paid = fields.Boolean(string="¿Pagado?", default=False)
    user_paid = fields.Many2one('res.users', string="Usuario que Pagó", readonly=True)
    date_paid = fields.Date(string="Fecha de Pago", readonly=True)


    @api.depends('worked_hours', 'overtime', 'holiday_hours', 'bonus', 'discount')
    def _compute_amount(self):
        for rec in self:
            rec.gross_amount = 0.00
            if rec.labor_cost_id:
                amount_overtime = rec.labor_cost_id.hour_cost_extra
                amount_holiday = rec.labor_cost_id.hour_cost_holiday
                rec.gross_amount = (rec.bonus + (rec.worked_hours * rec.labor_cost_id.hour_cost_normal) +
                                    (rec.overtime * amount_overtime) +
                                    (rec.holiday_hours * amount_holiday))
                rec.net_amount = rec.gross_amount - rec.discount
            
    @api.depends('employee_id', 'payroll_id.date_start', 'payroll_id.date_end')
    def _compute_attendance(self):
        for rec in self:
            rec.worked_days = 0.0
            rec.worked_hours = 0.0
            rec.overtime = 0.0
            rec.holiday_hours = 0.0
            season_costo = self.env['hr.season.labor.cost'].search([('active', '=', True),
                                                                    ('date_start', '<=', rec.payroll_id.date_start),
                                                                    ('date_end', '>=', rec.payroll_id.date_end)], limit=1)
            if not season_costo:
                raise ValidationError('No hay una temporada activa para calcular el costo laboral. Por favor, cree y active una temporada en Costo Laboral por Temporada.')
            rec.labor_cost_id = season_costo.id
            season_costo.hour_cost_normal
            
            
            if rec.employee_id and rec.payroll_id:
                attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('check_in', '>=', rec.payroll_id.date_start),
                    ('check_in', '<=', rec.payroll_id.date_end),
                ])
                if not attendances:
                    raise ValidationError('No se encontraron asistencias para el empleado %s en el período seleccionado.' % rec.employee_id.name)
                # Calcular horas trabajadas, días trabajados, horas extras y horas de vacaciones
                for att in attendances:
                    rec.worked_hours += att.worked_hours
                    rec.overtime += att.overtime
                    rec.holiday_hours += att.holiday_hours

    def action_paid(self):
        self.ensure_one()
        self.write({
            'is_paid': True,
            'user_paid': self.env.user.id,
            'date_paid': fields.Date.today()
        })