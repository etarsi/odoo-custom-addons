# -*- coding: utf-8 -*-
{
    'name': "sebigus_preventa",

    'summary': """
        Analisis de preventa 
        """,

    'description': """
        Preventa  Reporte de gestion para el analisis del avanza de la preventa
    """,

    'author': "Javeir Pepe",
    'website': "https://www.linkedin.com/in/javier-pepe-58b69410/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',
    'application': True,
    'sequence': -100,

    # any module necessary for this one to work correctly
    'depends': ['base', 'website','stock', 'sale', 'website_sale'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
      # 'views/templates.xml',
      # 'views/pedidos_online.xml',
      # 'views/view_order_form.xml',
        'views/preventa.xml',
        'views/catalogo.xml',
      # 'views/sale_product.xml',
      # 'views/sale_order_portal.xml',
      # 'reports/report_saleorder.xml',
      # 'views/report_saleorder_confirm.xml',
        'views/menu.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
