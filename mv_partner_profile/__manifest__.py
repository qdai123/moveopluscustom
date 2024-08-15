# -*- coding: utf-8 -*-
{
    "name": "MV Partner Profile",
    "version": "1.0.0",
    "category": "Moveoplus/MV Partner Profile",
    "description": """This module adds a new feature of the partner add-on to manage the partner profile.""",
    "author": "MOVEOPLUS System Development Team",
    "depends": [
        # Odoo
        "base",
        "portal",
        # Moveoplus
        "mv_base",
    ],
    "data": [
        # SECURITY
        "security/ir.model.access.csv",
        # VIEWS
        "views/res_partner_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
    "auto_install": False,
}
