# -*- coding: utf-8 -*-
{
    "name": "Inventory",
    "version": "1.0.0.17",
    "countries": ["vi"],
    "category": "Moveoplus/Inventory",
    "description": "Base on Inventory modules and Related modules to customize new features",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": ["base", "stock", "biz_stock_qrcode"],
    "data": [
        # SECURITY
        "security/stock_security.xml",
        # 'security/ir.model.access.csv',
        # MENU
        "menu/stock_menu.xml",
        # VIEWS
        "views/stock_quant_view.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
