# -*- coding: utf-8 -*-
{
    "name": "MV eCommerce",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV eCommerce",
    "description": "Base on eCommerce module to customize new features",
    "author": "Phat Dang <phat.dangminh@moveoplus.com>",
    "depends": [
        # Odoo
        "website_sale",
        "website_sale_loyalty",
        # Moveoplus
    ],
    "data": [
        # VIEWS
        "views/templates.xml",
        "views/website_sale_delivery_templates.xml",
    ],
    "bootstrap": True,
    "assets": {
        "web.assets_fontend": [],
    },
    "license": "LGPL-3",
    "application": True,
}
