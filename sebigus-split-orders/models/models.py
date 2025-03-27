
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

# NUEVO MODELO DE CONCIONES PARA EL M2M
class CondicionVenta(models.Model):
    _name = 'condicion.venta'
    _description = 'Condiciones de Venta'

    condiciones_selection = [
        ('A', 'Condición A'),
        ('B', 'Condición B'),
        ('C', 'Condición C'),
        ('D', 'Condición D'),
        ('E', 'Condición E')]
    condicion = fields.Selection(condiciones_selection, string="Condición")
    #condicion = fields.Char(string="Condición")
    porcentaje = fields.Float(string="Porcentaje (%)")
    name = fields.Char(string="Nombre")

# RES PARTNER
class ResPartner(models.Model):
    _inherit = 'res.partner'

    condicion_venta = fields.Selection([('A', 'Condición A'),('B', 'Condición B'),('C', 'Condición C'),('D', 'Condición D'),('E', 'Condición E')], string="Condición de Venta")

# SALE ORDER
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # CALL WIZARD
    def action_split_and_cancel_order(self):
        return {
            'name': 'Confirmación de Orden de Venta',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'sale.order.split.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    splitted = fields.Boolean(string='Splitted', default=False, copy=False)
    condicion_venta_selection = [
        ('A', 'Condición A'),
        ('B', 'Condición B'),
        ('C', 'Condición C'),
        ('D', 'Condición D'),
        ('E', 'Condición E')]
    condicion_venta = fields.Selection(condicion_venta_selection, string="Permiso")
    available_condiciones = fields.Many2many('condicion.venta', compute='_compute_available_condiciones') # DISPONIBLES
    # condicion_m2m = fields.Many2many('condicion.venta', string="Condición de Venta", domain="[('id', 'in', available_condiciones)]", limit=1) # SELECTOR
    # condicion_m2m = fields.Many2one('condicion.venta', string="Condición de Venta", domain="[('id', 'in', available_condiciones)]") # SELECTOR
    condicion_m2m = fields.Many2one('condicion.venta', string="Condición de Venta") # SELECTOR
    condicion_m2m_numeric = fields.Char(string="Condición de Venta (%)", readonly=True)
    #company_default = fields.Many2one('res.company', 'Compañia a facturar')

    @api.constrains('condicion_m2m')
    def check_condicion_m2m_count(self):
      if self.condicion_m2m:
        if len(self.condicion_m2m) > 1:
            raise ValidationError("Please select only one option.")

    # OVERRIDE DE ONCHANGE
    @api.onchange("partner_id")
    def onchange_partner_id(self):
        res = super().onchange_partner_id()
        self.condicion_venta = self.partner_id.condicion_venta
        self.condicion_m2m = False # RESETEAR SELECTOR
        self.condicion_m2m_numeric = False
        return res

    # ACTUALIZA LOS CHECKBOXES DISPONIBLES (available_condiciones)
    @api.depends('condicion_venta')
    def _compute_available_condiciones(self):
        for partner in self:
            if partner.condicion_venta:
                if partner.partner_id:
                  if partner.condicion_venta == 'A':
                       partner.available_condiciones = [(6, 0, self.env['condicion.venta'].search([('condicion', '=', 'A')]).ids)]
                  elif partner.condicion_venta == 'B':
                       partner.available_condiciones = [(6, 0, self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B'])]).ids)]
                  elif partner.condicion_venta == 'C':
                       partner.available_condiciones = [(6, 0, self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B', 'C'])]).ids)]
                  elif partner.condicion_venta == 'D':
                       partner.available_condiciones = [(6, 0, self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B', 'C', 'D'])]).ids)]
                  elif partner.condicion_venta == 'E':
                       partner.available_condiciones = [(6, 0, self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B', 'C', 'D', 'E'])]).ids)]
                else:
                    partner.available_condiciones = [(5, 0, 0)]
            else:
                partner.available_condiciones = [(5, 0, 0)]

    # ONCHANGE
    @api.onchange('condicion_venta')
    def _onchange_condicion_venta(self):
        for partner in self:
            partner.condicion_m2m = False # RESETEAR SELECTOR

    # ONCHANGE
    @api.onchange('condicion_m2m')
    def _onchange_condicion_venta(self):
        for partner in self:
            if partner.condicion_m2m:
                try:

                    # ANULO LOS PARÁMETROS DEL SISTEMA
                    # numeric_value = self.env['ir.config_parameter'].sudo().get_param('condicion.parameter_' + partner.condicion_m2m.condicion)

                    condicion_record = self.env['condicion.venta'].sudo().search([('condicion', '=', partner.condicion_m2m.condicion)], limit=1)
                    if condicion_record:
                        numeric_value = condicion_record.porcentaje
                    else:
                        numeric_value = 0  # Default value if no record is found
                    _logger.info('//// Valor de numeric_value: %s', numeric_value)

                    if numeric_value:
                        partner.condicion_m2m_numeric = float(numeric_value)
                    elif numeric_value == 0:
                        partner.condicion_m2m_numeric = 0.0
                    else:
                        artner.condicion_m2m_numeric = False
                    _logger.info('//// Valor de partner.condicion_m2m_numeric: %s', partner.condicion_m2m_numeric)

                except Exception as e:
                    raise UserError("Error fetching numeric value: %s" % str(e))
            else:
                partner.condicion_m2m_numeric = False

    # CREATE
    @api.model
    def create(self, vals):
        if 'partner_id' in vals:
            partner = self.env['res.partner'].search([('id', '=', vals['partner_id'])])
            vals['condicion_venta']=partner.condicion_venta
        if 'condicion_m2m' in vals:
            partner = self.env['res.partner'].search([('id', '=', vals['partner_id'])])
            condicion_id = self.env['condicion.venta'].search([('id', '=', vals['condicion_m2m'])])
            vals['condicion_m2m_numeric']=condicion_id.porcentaje

        if vals.get('condicion_venta'):
            condicion_ids = []
            if vals['condicion_venta'] == 'A':
                condicion_ids = self.env['condicion.venta'].search([('condicion', '=', 'A')]).ids
            elif vals['condicion_venta'] == 'B':
                condicion_ids = self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B'])]).ids
            elif vals['condicion_venta'] == 'C':
                condicion_ids = self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B', 'C'])]).ids
            elif vals['condicion_venta'] == 'D':
                condicion_ids = self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B', 'C', 'D'])]).ids
            elif vals['condicion_venta'] == 'E':
                condicion_ids = self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B', 'C', 'D', 'E'])]).ids
            vals['available_condiciones'] = [(6, 0, condicion_ids)]

        return super(SaleOrder, self).create(vals)

    # WRITE
    def write(self, vals):
        if vals.get('condicion_venta'):
            condicion_ids = []
            if vals['condicion_venta'] == 'A':
                condicion_ids = self.env['condicion.venta'].search([('condicion', '=', 'A')]).ids
            elif vals['condicion_venta'] == 'B':
                condicion_ids = self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B'])]).ids
            elif vals['condicion_venta'] == 'C':
                condicion_ids = self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B', 'C'])]).ids
            elif vals['condicion_venta'] == 'D':
                condicion_ids = self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B', 'C', 'D'])]).ids
            elif vals['condicion_venta'] == 'E':
                condicion_ids = self.env['condicion.venta'].search([('condicion', 'in', ['A', 'B', 'C', 'D', 'E'])]).ids
            vals['available_condiciones'] = [(6, 0, condicion_ids)]
        return super(SaleOrder, self).write(vals)
