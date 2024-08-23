# -*- coding: utf-8 -*-
{
    "name": "Base",
    "version": "1.0.0.17",
    "countries": ["vi"],
    "category": "Moveoplus/Base",
    "description": """
The kernel of Moveo Plus, needed for all installation.
===================================================
    """,
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": ["base", "base_setup", "mail"],
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
