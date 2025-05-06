{
    'name': "Sale Order Split",
    'summary': "Split sale orders into multiple orders with customizable quantities and company assignments.",
    'description': """
        This module allows users to split sale orders into multiple orders, each with customizable quantities and company assignments. 
        Users can specify the percentage of quantity to assign to each sale order and choose the company for each split order. 
        After the split, the original sale order is canceled, and links to it are added in the new sale orders.
    """,
    "category": "Accounting Management",
    'author': "Sebigus SRL, KleinerZuloaga",
    "license": "AGPL-3",
    'version': '15.0.1.0.0',
    'depends': ['sale'],
    'data': [
        'views/res_partner.xml',
        'views/sale_order.xml',
        'views/sale_order_views.xml',
        'views/condicion_venta.xml',
        'security/ir.model.access.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
