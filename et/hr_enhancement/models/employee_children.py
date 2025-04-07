from odoo import models, fields, api

class EmployeeChildren(models.Model):
    _name = 'employee.children'

    parent_id = fields.Many2one('hr.employee')
    name = fields.Char('Nombre y Apellido')
    age = fields.Integer('Edad')    
