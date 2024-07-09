# -*- coding: utf-8 -*-
{
    "name": "MV Invoicing",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV Invoicing",
    "description": "Base on Invoicing modules and Related modules to customize new features",
    "author": "Phat Dang <phat.dangminh@moveoplus.com>",
    "depends": [
        # Odoo
        "account",
        # Moveoplus
        "mv_base",
    ],
    "data": [
        # SECURITY
        "security/ir.model.access.csv",
        # VIEWS
        "views/report_invoice.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
