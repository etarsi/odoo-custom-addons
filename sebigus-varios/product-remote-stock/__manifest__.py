# -*- coding: utf-8 -*-
{
    'name': "product-remote-stock",

    'summary': """
        Actualza stock remoto""",

    'description': """
        remote stock
    """,

    'author': "Javier Pepe Company",
    'website': "https://www.linkedin.com/in/javier-pepe-58b69410",

    'category': 'Uncategorized',
    'version': '0.1',
    'application': True,
    'sequence': -100,

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock'],

    # always loaded
    'data': [
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
}
