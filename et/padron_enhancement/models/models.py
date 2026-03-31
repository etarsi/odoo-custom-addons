# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class web_enhancement(models.Model):
#     _name = 'web_enhancement.web_enhancement'
#     _description = 'web_enhancement.web_enhancement'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
