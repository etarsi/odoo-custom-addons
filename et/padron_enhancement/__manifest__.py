# -*- coding: utf-8 -*-
{
    'name': "padron_enhancement",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Este modulo es para almacenar el padrón de ARBA y AGIP de los clientes y tener las RETENCIONES Y PERCEPCIONES actualizadas en el sistema, para luego poder usarlas en los procesos de venta y compra.
    """,

    'author': "Sebigus",
    'website': "http://www.one.sebigus.com.ar",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base', 'web', 'account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/ar_padron_iibb_views.xml',
        'views/menu.xml',
    ],
    'application': False,
}
