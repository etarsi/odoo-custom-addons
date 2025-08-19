# -*- coding: utf-8 -*-
{
    'name': "hr_enhancement",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Este modulo integra en empleados el modulo de recursos humanos.
    """,

    'author': "Sebigus",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['hr', 'base', 'hr_attendance', 'web'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        #Ingreso de datos por defecto
        'data/res_groups_data.xml',
        'data/hr_license_type_data.xml',
        #Vista
        'views/hr_license_views.xml',
        'views/hr_location_views.xml',
        'views/hr_employee_form_views.xml',
        'views/hr_employee_children_views.xml',
        'views/hr_season_labor_cost_views.xml',
        'views/hr_license_type_views.xml',
        'views/hr_employee_salary_views.xml',
        'views/hr_payroll_salary_views.xml',
        'views/hr_work_schedule_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_holiday_custom_views.xml',
        'views/res_config_views.xml',
        'views/menu.xml',
        'views/views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_enhancement/static/src/js/handle_service.js',
        ],
    },
}
