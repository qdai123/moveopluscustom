# -*- coding: utf-8 -*-
{
    "name": "MV Base",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV Base",
    "description": """
    The kernel of MOVEO PLUS, needed for all installation.
    ===================================================
    """,
    "author": "Phat Dang <phat.dangminh@moveoplus.com>",
    "depends": ["base", "base_setup"],
    "data": [
        # SECURITY
        "security/mv_base_groups.xml",
        "security/mv_base_security.xml",
        "security/ir.model.access.csv",
        # VIEWS
        "views/res_partner_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
    "auto_install": True,
}
