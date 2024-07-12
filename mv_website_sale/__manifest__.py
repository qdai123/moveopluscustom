# -*- coding: utf-8 -*-
{
    "name": "MV eCommerce",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV eCommerce",
    "description": """
        === Base on eCommerce module to customize new features ===
        - Odoo Inherits: website_sale, website_sale_loyalty
        - Moveoplus Inherits: mv_sale
    """,
    "author": "Phat Dang <phat.dangminh@moveoplus.com>",
    "depends": [
        # Odoo
        "website_sale",
        "website_sale_loyalty",
        # Moveoplus
        "mv_sale",
    ],
    "data": [
        # TEMPLATE VIEWS
        "views/portal_templates.xml",
        # "views/website_sale_delivery_templates.xml",
        "views/templates.xml",
    ],
    "bootstrap": True,
    "assets": {
        "web.assets_fontend": [],
    },
    "license": "LGPL-3",
    "application": True,
}
