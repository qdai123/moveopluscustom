# -*- coding: utf-8 -*-
{
    "name": "eCommerce",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/eCommerce",
    "description": """
=== Base on eCommerce module to customize new features ===
- Odoo Inherits: website_sale, website_sale_loyalty
- Moveoplus Inherits: mv_sale
    """,
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": ["website_sale", "website_sale_loyalty", "mv_sale"],
    "data": [
        # TEMPLATE VIEWS
        "views/portal_templates.xml",
        # "views/website_sale_delivery_templates.xml",
        "views/templates.xml",
        "views/website_sale_comparison_template.xml",
    ],
    "bootstrap": True,
    "assets": {"web.assets_fontend": []},
    "license": "LGPL-3",
    "application": True,
}
