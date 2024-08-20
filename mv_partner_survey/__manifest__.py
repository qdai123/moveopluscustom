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
        "portal",
        # Moveoplus
        "mv_base",
    ],
    "data": [
        # DATA
        "data/mv_partner_survey_data.xml",
        # SECURITY
        "security/ir.model.access.csv",
        # VIEWS
        # "views/res_partner_views.xml",
        "views/mv_partner_area_views.xml",
        "views/partner_area_menu.xml",
    ],
    "license": "LGPL-3",
    "application": True,
    "auto_install": False,
}
