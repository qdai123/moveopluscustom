# -*- coding: utf-8 -*-
{
    "name": "Dealer Management System (DMS)",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/Dealer Management System",
    "description": """
A DMS is a comprehensive tool that helps dealerships improve efficiency, 
increase revenue, and enhance customer satisfaction by providing a unified view of all dealership operations.
    """,
    "summary": "Help dealerships improve efficiency, increase revenue, and enhance customer satisfaction.",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS System Development Team",
    "depends": ["contacts", "portal", "biz_vn_address", "mv_base", "mv_sale"],
    "data": [
        # DATA
        "data/mv_dms_data.xml",
        "data/mv_brand_data.xml",
        "data/mv_continent_data.xml",
        "data/mv_region_data.xml",
        # SECURITY
        "security/security.xml",
        "security/ir.model.access.csv",
        # VIEWS
        "views/mv_brand_views.xml",
        "views/mv_brand_category_views.xml",
        "views/mv_brand_proportion.xml",
        "views/mv_region_views.xml",
        "views/mv_product_attribute_views.xml",
        "views/mv_product_product_views.xml",
        "views/mv_service_views.xml",
        "views/mv_service_detail_views.xml",
        "views/mv_shop_views.xml",
        "views/mv_shop_category_views.xml",
        "views/mv_partner_survey_views.xml",
        # WIZARD
        # MENU
        "views/menus.xml",
    ],
    "bootstrap": True,
    "assets": {
        "web.assets_backend": ["mv_dms/static/src/scss/dms_style.scss"],
    },
    "license": "LGPL-3",
    "application": True,
    "auto_install": False,
}
