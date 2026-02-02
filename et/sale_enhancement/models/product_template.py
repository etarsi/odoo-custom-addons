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

    # al crear un producto el taxes_id debe tener iva 21 y percepcion iibb caba aplicada de las 3 empresas 2, 3 y 4
    @api.model
    def create(self, vals):
        product = super(ProductTemplateInherit, self).create(vals)
        product.taxes_id_update()
        return product

    def taxes_id_update(self):
        self.ensure_one()
        iva_21_ids = self.env['account.tax'].search([('type_tax_use', '=', 'sale'), ('amount', '=', 21), ('name', '=', 'IVA 21%')])
        percepcion_iibb_caba_ids = self.env['account.tax'].search([('name', '=', 'Percepción IIBB CABA Aplicada'), ('type_tax_use', '=', 'sale')])
        taxes_ids = []
        if percepcion_iibb_caba_ids and iva_21_ids:
            iva_21 = iva_21_ids.filtered(lambda r: r.company_id.id in [2,3,4])
            
            percepcion_iibb_caba = percepcion_iibb_caba_ids.filtered(lambda r: r.company_id.id in [2,3,4])
            taxes_ids.extend(iva_21)
            taxes_ids.extend(percepcion_iibb_caba)
        if taxes_ids:
            self.taxes_id = [(6, 0, [tax.id for tax in taxes_ids])]
            _logger.info(f"Producto {self.name} actualizado con impuestos IVA 21% y Percepción IIBB CABA Aplicada.")