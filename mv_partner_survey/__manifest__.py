# -*- coding: utf-8 -*-
{
    "name": "MV Partner Survey",
    "version": "1.0.0",
    "category": "Moveoplus/Partner Survey",
    "description": """
Create base detail of partner surveys
=====================================
(Update later)
    """,
    "summary": "Carry out detailed surveys by partner agencies of Moveo Plus Company",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS System Development Team",
    "depends": ["base", "contacts", "portal", "biz_vn_address", "mv_base"],
    "data": [
        # DATA
        "data/partner_survey_data.xml",
        # SECURITY
        "security/security.xml",
        "security/ir.model.access.csv",
        # VIEWS
        "views/mv_brand_proportion.xml",
        "views/mv_brand_views.xml",
        "views/mv_partner_area_views.xml",
        "views/mv_partner_survey_views.xml",
        "views/mv_shop_views.xml",
        # MENU
        "views/partner_area_menu.xml",
        "views/menus.xml",
    ],
    "license": "LGPL-3",
    "application": True,
    "auto_install": False,
}
