# -*- coding: utf-8 -*-
{
    'name': "debt_composition",

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
    'depends': ['base', 'account', 'account_payment_group'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'data/actions.xml',
        'data/menu.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # assets are loaded in the backend
    'assets': {
        'web.assets_backend': [
            'debt_composition/static/src/js/report_debt_composition_client.js',
        ],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
