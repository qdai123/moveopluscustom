# -*- coding: utf-8 -*-
{
    'name': 'MV Stock QR-Code',
    'version': '17.0.1.0',
    'category': 'Moveoplus/MV Stock QR-Code',
    'description': "Base on Biz Stock QR-Code module to customize new features",
    'author': 'Phat Dang <phat.dangminh@moveoplus.com>',
    'depends': [
        # Biz
        'biz_stock_qrcode',
    ],
    'data': [
        # SECURITY
        'security/ir.model.access.csv',
        # VIEWS
        'views/stock_move_views.xml',
        'views/stock_move_line_views.xml',
        'views/stock_lot_views.xml',
    ],
    'license': 'LGPL-3',
    'application': True,
}
