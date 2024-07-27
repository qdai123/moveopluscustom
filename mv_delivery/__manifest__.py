# -*- coding: utf-8 -*-
{
    "name": "MV Delivery",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV Delivery",
    "description": "Base on Delivery module to customize new features",
    "author": "MOVEOPLUS system development team",
    "depends": [
        # Odoo
        "delivery",
        "stock_delivery",
    ],
    "data": [
        # VIEWS
        "views/sale_order_views.xml",
        "views/stock_picking_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
