# -*- coding: utf-8 -*-
{
    "name": "Human Resource Management",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/HRM",
    "description": """
- Base on HRM modules and Related modules to customize new features
- Configuration Basic Salary from MOVEOPLUS Company
    """,
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": ["hr", "hr_contract", "hr_recruitment", "hr_payroll"],
    "data": [
        # SECURITY
        "security/ir.model.access.csv",
        # VIEWS
        "views/basic_salary_views.xml",
        "views/hr_contract_views.xml",
        "views/hr_job_views.xml",
        "views/hr_employee_views.xml",
        "views/category_job_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
