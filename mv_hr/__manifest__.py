# -*- coding: utf-8 -*-
{
    'name': 'Basic salary',
    'description': """
        - Config basic salary
    """,
    'category': '',
    'version': '17.0',
    'author': '',
    'depends': [
        'hr_payroll',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/basic_salary_views.xml',
        'views/hr_contract_views.xml',
        'views/category_job_views.xml',
        'views/hr_job_views.xml',
        'views/hr_employee_views.xml'
    ],
}
