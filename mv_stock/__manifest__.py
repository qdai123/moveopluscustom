# -*- coding: utf-8 -*-
{
    "name": "Inventory",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/Inventory",
    "description": "Base on Inventory modules and Related modules to customize new features",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": ["stock", "mv_base", "biz_stock_qrcode"],
    "data": [
        # SECURITY
        "security/stock_security.xml",
        "security/ir.model.access.csv",
        # WIZARDS
        "wizards/mv_history_stock_wizard_view.xml",
        # VIEWS
        "views/stock_warehouse_views.xml",
        "views/stock_quant_view.xml",
        "views/mv_history_stock_views.xml",
        # MENU
        "menu/stock_menu.xml",
    ],
    "bootstrap": True,
    "assets": {
        "web.assets_backend": [
            "mv_stock/static/src/**/*.js",
            "mv_stock/static/src/**/*.xml",
            "mv_stock/static/src/scss/*.scss",
            "mv_stock/static/src/views/**/*",
        ],
    },
    "license": "LGPL-3",
    "application": True,
}
