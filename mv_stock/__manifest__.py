# -*- coding: utf-8 -*-
{
    'name': 'MV Stock',
    'version': '17.0.1.0',
    'category': 'Moveoplus/MV Stock',
    'description': "",
    'author': '',
    'depends': [
        'base',
        'stock',
        'biz_stock_qrcode',
    ],
    'data': [
        # SECURITY
        'security/stock_security.xml',
        # 'security/ir.model.access.csv',
        # MENU
        'menu/stock_menu.xml',
        # VIEWS
        'views/stock_quant_view.xml',
    ],
    'license': 'LGPL-3',
    'application': True,
}
