# -*- coding: utf-8 -*-
{
    "name": "Stock QR-Code",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/Stock QR-Code",
    "description": "Base on Biz Stock QR-Code module to customize new features",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": ["stock", "stock_barcode", "biz_stock_qrcode"],
    "data": [
        # SECURITY
        "security/ir.model.access.csv",
        # VIEWS
        "views/stock_picking_views.xml",
        "views/stock_move_views.xml",
        "views/stock_move_line_views.xml",
        "views/stock_lot_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mv_stock_qrcode/static/src/**/*.js",
            "mv_stock_qrcode/static/src/**/*.xml",
        ],
    },
    "license": "LGPL-3",
    "application": True,
}
