# -*- coding: utf-8 -*-
{
    'name': " libro-mayo",

    'summary': """
        Vista de libro mayor sumarizada""",

    'description': """
        Libro mayor resumen 
    """,

    'author': "Javier Pepe Company",
    'website': "https://www.linkedin.com/in/javier-pepe-58b69410",

    'category': 'Uncategorized',
    'version': '0.1',
    'application': True,
    'sequence': -100,

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    "data": [
        "views/libro_mayor_views.xml",
        "security/ir.model.access.csv"
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
}
