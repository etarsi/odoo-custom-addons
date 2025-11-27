# -*- coding: utf-8 -*-
{
    'name': "layout_qweb_custom",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Module to customize QWeb layouts para diversas vistas y reportes.
    """,

    'author': "Ezequiel Tarsitano",
    'website': "http://www.yourcompany.com",
    'category': 'Uncategorized',
    'version': '0.1',
    
    'depends': ['base', 'web'],
    "data": [
        "views/report_layout_custom.xml",
        "data/report_layout_record.xml",
    ],
}
