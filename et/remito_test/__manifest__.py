{
    'name': 'Remito JS Test',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Prueba de apertura de múltiples PDFs con JS',
    'author': 'Tu Nombre',
    'depends': ['base'],
    'data': [
        'views/remito_test_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'remito_test_js/static/src/js/remito_open.js',
        ],
    },
    'installable': True,
    'application': False,
}
