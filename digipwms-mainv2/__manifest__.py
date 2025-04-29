# -*- coding: utf-8 -*-
{
    'name': "digipwmsv2",

    'summary': """
        Comunicion transferecias digipwms                                         
        """,

    'description': """
        DigipWMS
    """,

    'author': "Javier Pepe, KleinerZuloaga",
    'website': "http://www.javierpepe.com",

    'category': 'Uncategorized',
    'version': '0.2',
    'application': True,
    'sequence': -100,

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock', 'sale', 'sale_stock', 'purchase', 'purchase_stock', 'stock_voucher', 'stock_enhancement2'],

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
