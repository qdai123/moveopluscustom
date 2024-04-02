# -*- coding: utf-8 -*-
{
    'name': 'MV Helpdesk',
    'version': '17.0.1.0',
    'category': 'Moveoplus/MV Helpdesk',
    'description': "Base on Helpdesk module to customize new features",
    'author': 'Phat Dang <phat.dangminh@moveoplus.com>',
    'depends': ['helpdesk'],
    'data': [
        # SECURITY
        'security/ir.model.access.csv',
        # VIEWS
        'views/helpdesk_ticket_product_moves_views.xml',
        'views/helpdesk_ticket_views.xml',
        # MENU
        'views/helpdesk_menus.xml',
    ],
    'license': 'LGPL-3',
    'application': True,
}
