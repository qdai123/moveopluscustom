# -*- coding: utf-8 -*-
{
    "name": "Dealer Management",
    "version": "1.0.0.17",
    "countries": ["vi"],
    "category": "Moveoplus/Dealer Management",
    "description": """
A DMS is a comprehensive tool that helps dealerships improve efficiency, 
increase revenue, and enhance customer satisfaction by providing a unified view of all dealership operations.
    """,
    "summary": "Carry out detailed surveys by partner agencies of Moveo Plus Company",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS System Development Team",
    "depends": ["base", "contacts", "portal", "biz_vn_address", "mv_base", "mv_sale"],
    "data": [
        # DATA
        "data/partner_survey_data.xml",
        # SECURITY
        "security/security.xml",
        "security/ir.model.access.csv",
        # VIEWS
        "views/mv_brand_views.xml",
        "views/mv_brand_proportion.xml",
        "views/mv_partner_area_views.xml",
        "views/mv_partner_survey_views.xml",
        "views/mv_product_attribute_views.xml",
        "views/mv_product_product_views.xml",
        "views/mv_shop_views.xml",
        # MENU
        "views/menus.xml",
    ],
    "license": "LGPL-3",
    "application": True,
    "auto_install": False,
}
