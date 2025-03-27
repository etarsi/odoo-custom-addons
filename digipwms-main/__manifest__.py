# -*- coding: utf-8 -*-
{
    'name': "digipwms",

    'summary': """
        Comunicion transferecias digipwms                                         
        """,

    'description': """
        DigipWMS
    """,

    'author': "JAvier Pepe, KleinerZuloaga",
    'website': "http://www.javierpepe.com",

    'category': 'Uncategorized',
    'version': '0.1',
    'application': True,
    'sequence': -100,

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock', 'sale', 'sale_stock', 'purchase', 'purchase_stock'],

    # always loaded
    'data': [
#        'security/ir.model.access.csv',
        'security/param.xml',
        'views/stock_picking_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
