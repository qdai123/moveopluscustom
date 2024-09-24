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
        "security/ir.model.access.csv",
        # WIZARDS
        "wizards/mv_history_stock_wizard_view.xml",
        # MENU
        "menu/stock_menu.xml",
        # VIEWS
        "views/stock_warehouse_views.xml",
        "views/stock_quant_view.xml",
        "views/mv_history_stock_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
    "bootstrap": True,
    "assets": {
        "web.assets_backend": [
            "mv_stock/static/src/**/*",
            "mv_stock/static/src/js/history_stock.js",
            "mv_stock/static/src/scss/mv_stock_style.scss",
            "mv_stock/static/src/xml/template_history_stock.xml",
        ],
    },
}
