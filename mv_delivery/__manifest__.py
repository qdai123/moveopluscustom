# -*- coding: utf-8 -*-
{
    "name": "Delivery",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/Delivery",
    "description": "Base on Delivery module to customize new features",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": ["delivery", "stock_delivery"],
    "data": [
        # VIEWS
        "views/sale_order_views.xml",
        "views/stock_picking_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
