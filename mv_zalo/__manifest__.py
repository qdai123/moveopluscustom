# -*- coding: utf-8 -*-
{
    "name": "Zalo OA",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/Zalo OA",
    "description": "Base on Zalo modules to customize new features",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": [
        # Odoo
        "account",
        "stock",
        # BIZ
        "biz_zalo",
        "biz_zalo_common",
        "biz_zalo_zns",
        # MOVEOPLUS
        "mv_account",
        "mv_base",
        "mv_sale",
    ],
    "data": [
        # DATA
        "data/ir_config_parameter.xml",
        "data/ir_cron_data.xml",
        # SECURITY
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        # VIEWS
        "views/account_move_views.xml",
        "views/stock_picking_views.xml",
        "views/res_partner_views.xml",
        "views/mv_compute_discount_line_views.xml",
        "views/mv_compute_warranty_discount_policy_line_views.xml",
        "views/res_config_settings_views.xml",
        # WIZARDS
        "wizard/zns_send_message_testing_wizard_views.xml",
        "wizard/zns_send_message_wizard_views.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
