# -*- coding: utf-8 -*-
{
    'name': "sale_enhancement",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Ezequiel Tarsitano",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale', 'delivery', 'sebigus-split-orders', 'stock_enhancement2', 'product', 'stock', 'contact'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        #reports
        'reports/report_saleorder_document.xml',
        #wizards
        'views/sale_order_tipo_venta_wizard.xml',
        #data
        'data/actions.xml',
        #views
        'views/templates.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/product_pricelist_view.xml',
        'views/sale_order_views_tree.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
