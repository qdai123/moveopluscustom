# -*- coding: utf-8 -*-
{
    'name': 'MV Website Helpdesk',
    'version': '17.0.1.0',
    'category': 'Moveoplus/MV Website Helpdesk',
    'description': "Base on Website Helpdesk module to customize new features",
    'author': 'Phat Dang <phat.dangminh@moveoplus.com>',
    'depends': [
        # Odoo
        'web',
        # Odoo (Enterprice)
        'website_helpdesk',
        # Moveoplus
        'mv_helpdesk',
    ],
    'data': [
        # SECURITY
        'security/ir.model.access.csv',
        # DATA
        'data/helpdesk_data.xml',
        # VIEWS
        'views/helpdesk_templates.xml',
    ],
    # 'bootstrap': True,
    # 'assets': {
    #     'web.assets_frontend': [
    #         'mv_website_helpdesk/static/**/*',
    #     ],
    # },
    'license': 'LGPL-3',
    'application': True,
}
