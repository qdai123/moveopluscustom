# -*- coding: utf-8 -*-
{
    "name": "Inventory",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/Inventory",
    "description": "Base on Inventory modules and Related modules to customize new features",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": ["base", "stock", "biz_stock_qrcode"],
    "data": [
        # SECURITY
        "security/stock_security.xml",
        'security/ir.model.access.csv',
        # WIZARDS
        "wizards/mv_history_stock_wizard_view.xml",
        # MENU
        "menu/stock_menu.xml",
        # VIEWS
        "views/stock_quant_view.xml",
        "views/mv_history_stock_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
