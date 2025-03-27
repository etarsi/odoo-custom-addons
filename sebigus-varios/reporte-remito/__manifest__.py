# -*- coding: utf-8 -*-
{
    'name': "reporte-remito",

    'summary': """
        Add packaging sum in views""",

    'description': """
        Product image
    """,

    'author': "Javier Pepe Company",
    'website': "https://www.linkedin.com/in/javier-pepe-58b69410",

    'category': 'Uncategorized',
    'version': '0.1',
    'application': True,
    'sequence': -200,

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock'],

    # always loaded
    'data': [
        'views/stock_picking.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
}
