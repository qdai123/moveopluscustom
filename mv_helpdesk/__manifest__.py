# -*- coding: utf-8 -*-
{
    "name": "MV Helpdesk",
    "version": "17.0.1.0",
    "category": "Moveoplus/MV Helpdesk",
    "description": "Base on Helpdesk module to customize new features",
    "author": "Phat Dang <phat.dangminh@moveoplus.com>",
    "depends": [
        # Odoo (Enterprise)
        "helpdesk",
        "helpdesk_stock",
        # BIZ
        "biz_stock_qrcode",
    ],
    "data": [
        # SECURITY
        "security/helpdesk_security.xml",
        "security/ir.model.access.csv",
        # DATA
        "data/mail_template_data.xml",
        "data/helpdesk_data.xml",
        "data/service_cron.xml",
        # VIEWS
        "views/helpdesk_ticket_product_moves_views.xml",
        "views/helpdesk_team_views.xml",
        "views/helpdesk_ticket_type_views.xml",
        "views/helpdesk_ticket_views.xml",
        # REPORT
        "report/helpdesk_stock_move_line_report_views.xml",
        # WIZARD
        "wizard/wizard_import_lot_serial_number_views.xml",
        # MENU
        "views/helpdesk_menus.xml",
    ],
    "license": "LGPL-3",
    "application": True,
}
