##############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
{
    'name': 'Exportacion SIRCAR',
    'version': '15.0.0.0.0',
    'category': 'Accounting',
    'sequence': 14,
    'summary': '',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
	'base','account','l10n_ar'
    ],
    'data': [
	'security/ir.model.access.csv',
	'account_view.xml'
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
