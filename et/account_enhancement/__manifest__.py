# -*- coding: utf-8 -*-
{
    'name': "account_enhancement",

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
    
    # assets are loaded in the backend
    'assets': {
        'web.assets_backend': [
            'account_enhancement/static/src/js/account_move.js',
        ],
    },
    # any module necessary for this one to work correctly
    'depends': ['account_check_printing', 'account_payment_group', 'l10n_latam_check', 'l10n_ar', 'account'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        #permissions
        'permisos/res_group.xml',
        'views/views.xml',
        'views/account_move_views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
