# -*- coding: utf-8 -*-
{
    'name': 'MV Web',
    'version': '17.0.1.0',
    'category': 'Moveoplus/MV Web',
    'description': "Base on Web Core module to customize new features",
    'author': 'Phat Dang <phat.dangminh@moveoplus.com>',
    'depends': [
        # Odoo
        'web',
        # Odoo (Enterprise)
        'web_enterpise',
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'mv_web/static/src/views/**/*',
        ],
    },
    'license': 'LGPL-3',
    'application': True,
}
