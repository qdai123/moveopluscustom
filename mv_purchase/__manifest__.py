# -*- coding: utf-8 -*-
{
    "name": "MV Purchase",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV Purchase",
    "description": "Base on Purchase modules and Related modules to customize new features",
    "author": "MOVEOPLUS system development team",
    "depends": [
        # Odoo
        "purchase",
        # Moveoplus
        "mv_base",
    ],
    "data": [
        # SECURITY
        # VIEWS
        "views/purchase_order_views.xml",
        # WIZARDS
    ],
    "license": "LGPL-3",
    "application": True,
}
