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
    tipo_pago = fields.Selection([
        ('semanal', 'Semanal'),
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
        ('dia', 'Día')
    ], string="Tipo de Pago", required=True, tracking=True)
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
    ], string="Tipo de Empleado a Pagar", required=True, tracking=True)
    #totales de la planilla
    total_amount = fields.Monetary(
        string="Total a Pagar",
        compute='_compute_total_amount',
        currency_field='currency_id',
        store=True
    )
    line_ids = fields.One2many('hr.payroll.salary.line', 'payroll_id', string="Detalles de Planilla", copy=True)

    @api.depends('line_ids.net_amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('net_amount'))
    
class HrPayrollSalaryLine(models.Model):
    _name = 'hr.payroll.salary.line'
    _description = 'Detalle de Planilla de Pago'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    payroll_id = fields.Many2one('hr.payroll.salary', string="Planilla", required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string="Empleado", domain="[('employee_type', '=', payroll_id.employee_type)]", required=True)
    job_id = fields.Many2one(related='employee_id.job_id', string="Puesto", store=True)
    contract_id = fields.Many2one('hr.contract', string="Contrato")  # Opcional, si tenés contratos
    worked_days = fields.Float('Días Trabajados', compute='_compute_attendance', store=True)
    worked_hours = fields.Float('Horas Trabajadas', compute='_compute_attendance', store=True)
    basic_amount = fields.Float('Sueldo Básico', help="Sueldo básico por el período")
    bonus = fields.Float('Bonos/Premios', default=0.0)
    discount = fields.Float('Descuentos', default=0.0)
    holidays = fields.Float('Días de Licencia', default=0.0)
    gross_amount = fields.Float('Total Bruto', compute='_compute_gross_amount', store=True)
    net_amount = fields.Float('Total Neto', compute='_compute_net_amount', store=True)
    note = fields.Char('Nota (Observaciones)')
    currency_id = fields.Many2one(
    'res.currency',
    string="Moneda",
    required=True,
    default=lambda self: self.env.company.currency_id.id
    )
    state = fields.Selection(related='payroll_id.state', string='Estado', store=True)
    

    @api.depends('basic_amount', 'bonus', 'discount')
    def _compute_gross_amount(self):
        for rec in self:
            rec.gross_amount = rec.basic_amount + rec.bonus

    @api.depends('gross_amount', 'discount')
    def _compute_net_amount(self):
        for rec in self:
            rec.net_amount = rec.gross_amount - rec.discount
            
    @api.depends('employee_id', 'payroll_id.date_start', 'payroll_id.date_end')
    def _compute_attendance(self):
        for rec in self:
            if rec.employee_id and rec.payroll_id:
                attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('check_in', '>=', rec.payroll_id.date_start),
                    ('check_in', '<=', rec.payroll_id.date_end),
                ])
                total_hours = sum(a.worked_hours for a in attendances)
                # O podés calcularlo manualmente si 'worked_hours' no existe:
                # total_hours = sum((a.check_out - a.check_in).total_seconds()/3600 for a in attendances if a.check_in and a.check_out)
                rec.worked_hours = total_hours
                # Suponiendo 8hs = 1 día trabajado
                rec.worked_days = total_hours / 8.0 if total_hours else 0.0
            else:
                rec.worked_hours = 0.0
                rec.worked_days = 0.0