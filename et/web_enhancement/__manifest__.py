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
    'depends': ['base', 'web', 'website', 'product', 'base_setup', 'stock'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        #'views/web_product_template.xml',
        'views/product_template_views.xml',
        #'views/website_menu.xml',
        'views/shop_gate.xml',
        'views/views.xml',
        'views/res_config_views.xml',
        'views/product_download_mark_views.xml',
        'views/menu_stock.xml',
        'views/templates.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'web_enhancement/static/src/js/handle_service.js',
        ],
        'web.assets_frontend': [
            'web_enhancement/static/src/js/zip_download.js',
        ],
    },
    'application': False,
}
