from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

RUBRO_COMPANY_MAPPING = {
    'JUGUETES': 3,
    'CARPAS': 3,
    'RODADOS INFANTILES': 3,
    'PISTOLAS DE AGUA': 4,
    'INFLABLES': 4,
    'PELOTAS': 4,
    'VEHICULOS A BATERIA': 4,
    'RODADOS': 2,
    'MAQUILLAJE': 2,
    'CABALLITOS SALTARINES': 2,
}


class ProductTemplateInherit(models.Model):
    _inherit = "product.template"

    company_ids = fields.Many2many('res.company', string='Compañias Permitidas', help='Compañias que pueden usar este producto.')
    name_alternative = fields.Char(string="Nombre Alternativo")
    active_alternative = fields.Boolean(string="Activo Alternativo", default=False, help="Si está activo, este producto se mostrara con su nombre alternativo.")
    excluyent_partner_ids = fields.Many2many(
        'res.partner',
        'product_template_excluyent_partner_rel',
        'product_tmpl_id',
        'partner_id',
        string='Clientes Excluyentes', 
        help="Clientes que tendran el nombre original del producto."
    )    

    
    def action_update_company_ids_value(self):
        self.ensure_one()
        products = self.env['product.template'].search([('sale_ok', '=', True)])
        if products:
            for product in products:
                product.update_company_ids_value()
                
    def update_company_ids_value(self):
        company_ids = []
        categorias = self.env['product.category'].search([('parent_id', '=', False)])
        if categorias:
            for categoria in categorias:
                if self.categ_id.parent_id and self.categ_id.parent_id.id == categoria.id:
                    rubro = categoria.name.upper().strip()
                    if rubro in RUBRO_COMPANY_MAPPING:
                        company_id = RUBRO_COMPANY_MAPPING[rubro]
                        company_ids.append(company_id)
        if company_ids:
            self.company_ids = [(6, 0, list(set(company_ids)))]
