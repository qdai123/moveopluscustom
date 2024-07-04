# -*- coding: utf-8 -*-
{
    "name": "MV Zalo",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV Zalo",
    "description": "Base on Zalo modules to customize new features",
    "author": "Phat Dang <phat.dangminh@moveoplus.com>",
    "depends": [
        # Odoo
        "account",
        "stock",
        # BIZ
        "biz_zalo",
        "biz_zalo_common",
        "biz_zalo_zns",
        # MOVEOPLUS
        "mv_sale",
    ],
    "data": [
        # DATA
        "data/ir_cron_data.xml",
        # SECURITY
        "security/ir.model.access.csv",
        # VIEWS
        "views/account_move_views.xml",
        "views/stock_picking_views.xml",
        "views/res_config_settings_views.xml",
        # WIZARDS
        "wizard/zns_send_message_wizard_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
