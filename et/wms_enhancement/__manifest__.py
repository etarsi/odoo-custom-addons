# -*- coding: utf-8 -*-
{
    'name': "wms_enhancement",

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
    'depends': ['base', 'sale', 'purchase', 'account', 'product', 'stock_erp', 'tms_service'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        #REPORTES
        'reports/tms_roadmap_report.xml',
        'data/action.xml',
        'views/wizard/tms_stock_picking_roadmap_wizard_views.xml',
        'views/wizard/import_container_excel_task_wizard_views.xml',
        'views/wizard/tms_roadmap_report_wizard_views.xml',
        'views/wizard/report_wms_task_factura_wizard_views.xml',
        'views/transfer_views.xml',
        'views/task_views.xml',
        'views/sale_order_views.xml',
        'views/invoice_views.xml',
        'views/product_lot.xml',
        'views/res_config_settings_views.xml',
        'views/tms_stock_picking_views.xml',
        'views/tms_roadmap_views.xml',
        'views/preselection_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wms_enhancement/static/src/js/selection_sum_list_transfer.js',
            'wms_enhancement/static/src/js/selection_sum_list_task.js',
        ],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
