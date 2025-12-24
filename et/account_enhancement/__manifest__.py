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
            #JS
            'account_enhancement/static/src/js/account_move.js',
            'account_enhancement/static/src/js/list_row_number.js',
            #XML
            'account_enhancement/static/src/xml/field_row_number.xml',
        ],
    },
    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'account_check_printing', 'account_payment_group', 'l10n_latam_check', 'l10n_ar', 'l10n_ar_reports','l10n_ar_afipws_fe', 'mail', 'sale', 'product', 'sale_enhancement', 'l10n_ar_ux', 'account_financial_report'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        # Data
        'data/group_pago.xml',
        'data/ir_cron.xml',
        'data/mail_template_invoice_facture.xml',
        'views/account_payment_group_suprimir_wizard_views.xml',
        'views/account_import_afip_facprov_wizard_views.xml',
        'data/action_payment_group.xml',
        #Reportes
        'wizard/generar_factura_wizard_views.xml',
        #Templates
        'template/report_payment_group_document_views.xml',
        #permissions
        'permissions/res_group.xml',
        'views/views.xml',
        'views/sale_refacturar_wizard_views.xml',
        'views/out_invoice_refacturar_wizard_views.xml',
        'views/report_account_payment_group.xml',
        'views/report_account_move.xml',
        'views/account_move_views.xml',
        'views/calendar_paid_views.xml',
        'views/report_pagos_fuera_fecha.xml',
        'views/account_payment_group_views.xml',
        'views/account_payment_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_line_views.xml',
        'views/report_factura_proveedor_views.xml',
        #'views/templates.xml',
        'views/menu.xml',
        'views/res_partner_debt_composition_report_views.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    
}
