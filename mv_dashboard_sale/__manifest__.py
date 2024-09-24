# -*- coding: utf-8 -*-
{
    "name": "Dashboard for Sales",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/Dashboard",
    "description": "Dashboard for Sales (Orders, Invoices, Customers, Products, etc.)",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": ["spreadsheet_dashboard", "ks_dashboard_ninja", "mv_sale"],
    "data": [
        # SECURITY
        "security/ir.model.access.csv",
        # DATA
        "data/default_dashboard_data.xml",
        # "data/default_dashboard_item_data.xml",
        # "data/default_dashboard_template_data.xml",
        # "data/dashboard.xml",
        # VIEWS
        "views/dashboard_sale_views.xml",
        # MENU
        "views/menus.xml",
    ],
    "bootstrap": True,
    "assets": {},
    "license": "LGPL-3",
    "application": True,
}
