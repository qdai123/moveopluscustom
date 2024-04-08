# -*- coding: utf-8 -*-
{
    'name': 'MV Helpdesk',
    'version': '17.0.1.0',
    'category': 'Moveoplus/MV Helpdesk',
    'description': "Base on Helpdesk module to customize new features",
    'author': 'Phat Dang <phat.dangminh@moveoplus.com>',
    'depends': [
        # Odoo (Enterpice)
        'helpdesk',
    ],
    'data': [
        # SECURITY
        'security/ir.model.access.csv',
        # DATA
        'data/mail_template_data.xml',
        'data/helpdesk_data.xml',
        'data/service_cron.xml',
        # VIEWS
        'views/helpdesk_ticket_product_moves_views.xml',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_ticket_type_views.xml',
        'views/helpdesk_ticket_views.xml',
        # MENU
        'views/helpdesk_menus.xml',
    ],
    'license': 'LGPL-3',
    'application': True,
}
