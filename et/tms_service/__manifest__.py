# -*- coding: utf-8 -*-
{
    'name': "tms_service",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Este modulo integra en Realizar el Ruteo de Servicio.
    """,

    'author': "Sebigus",
    'website': "http://www.sebigus.com.ar",
    'application': True,
    'installable': True,
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': 'v.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'contacts', 'stock', 'sale', 'delivery'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/tms_stock_picking_server_actions.xml',
        'views/tms_stock_picking_views.xml',
        'views/menu.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
