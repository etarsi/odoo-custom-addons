# -*- coding: utf-8 -*-
{
    'name': "report_enhancement",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Detalle de facturación por cliente / comercial y rubro
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account_enhancement', 'report_xlsx', 'sale'],
    'assets': {
        'web.assets_backend': [
            'report_enhancement/static/src/js/action_report_xlsx.js',
        ],
    },
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        #TEMPLATES
        'report/templates/report_balance_addition_base.xml',
        'views/report_balance_addition.xml',
        #REPORTS
        'report/report_balance_addition_reports.xml',
        'views/report_factura_rubros_temp_views.xml',
        'views/report_factura_rubros_temp_nav_views.xml',
        'views/wizards/report_balance_addition_wizard_views.xml',
        'views/wizards/report_composition_debt_wizard_views.xml',
        'views/report_factura_rubros_temp_dn_views.xml',
        'views/menu.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'aplication': True,
}
