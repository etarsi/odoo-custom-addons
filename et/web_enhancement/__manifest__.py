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
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base', 'web', 'website', 'product'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/product_grid_qweb.xml',
        'views/website_menu.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_enhancement/static/src/js/handle_service.js',
        ],
    },
    'application': False,
}
