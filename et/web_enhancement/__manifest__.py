# -*- coding: utf-8 -*-
{
    'name': "web_enhancement",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Este modulo es para la web de log de reconexion del odoo partner
    """,

    'author': "Sebigus",
    'website': "http://www.one.sebigus.com.ar",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'web', 'website', 'product'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/web_product_templates.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_enhancement/static/src/js/handle_service.js',
        ],
    },
}
