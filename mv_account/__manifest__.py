# -*- coding: utf-8 -*-
{
    "name": "MV Invoicing",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV Invoicing",
    "description": "Base on Invoicing modules and Related modules to customize new features",
    "author": "MOVEOPLUS system development team",
    "depends": [
        # Odoo
        "account",
        # Moveoplus
        "biz_viettel_sinvoice_v2",
        "mv_base",
    ],
    "data": [
        # SECURITY
        "security/ir.model.access.csv",
        # VIEWS
        "views/mv_account_move_views.xml",
        "views/report_invoice.xml",
        # WIZARDS
        "wizard/account_payment_register_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
