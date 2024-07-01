# -*- coding: utf-8 -*-
{
    "name": "MV Zalo",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV Zalo",
    "description": "Base on Zalo modules to customize new features",
    "author": "Phat Dang <phat.dangminh@moveoplus.com>",
    "depends": [
        # Odoo
        "stock",
        # BIZ
        "biz_zalo",
        "biz_zalo_common",
        "biz_zalo_zns",
        # MOVEOPLUS
        "mv_sale",
    ],
    "data": [
        # SECURITY
        "security/ir.model.access.csv",
        # VIEWS
        "views/stock_picking_views.xml",
        # WIZARDS
        "wizard/zns_send_message_wizard_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
