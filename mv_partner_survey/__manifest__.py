# -*- coding: utf-8 -*-
{
    "name": "MV Partner Survey",
    "version": "1.0.0",
    "category": "Moveoplus/MV Partner Survey",
    "description": """This module adds a new feature of the partner add-on to manage the partner survey.""",
    "author": "MOVEOPLUS System Development Team",
    "depends": [
        # Odoo
        "base",
        "contacts",
        "portal",
        # Biztech
        "biz_vn_address",
        # Moveoplus
        "mv_base",
    ],
    "data": [
        # DATA
        "data/partner_survey_data.xml",
        # SECURITY
        "security/security.xml",
        "security/ir.model.access.csv",
        # VIEWS
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
