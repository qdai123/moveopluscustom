# -*- coding: utf-8 -*-
{
    "name": "Website Helpdesk",
    "version": "17.0.1.0",
    "countries": ["vi"],
    "category": "Moveoplus/Website Helpdesk",
    "description": "Base on Website Helpdesk module to customize new features",
    "website": "https://moveoplus.com/cau-chuyen-moveo/",
    "author": "MOVEOPLUS system development team",
    "depends": [
        # Odoo
        "barcodes",
        "website",
        "web",
        # Odoo (Enterprise)
        "website_helpdesk",
        # Moveoplus
        "mv_helpdesk",
        "mv_website",
    ],
    "data": [
        # SECURITY
        "security/ir.model.access.csv",
        # DATA
        "data/website_helpdesk_data.xml",
        "data/ir_sequence_data.xml",
        # VIEWS
        "views/helpdesk_team_views.xml",
        "views/helpdesk_ticket_views.xml",
        "views/helpdesk_templates.xml",
        "views/claim_warranty_portal_views.xml",
        # MENU
        "views/website_menus.xml",
        # DEFAULT DATA
        "data/default_data_helpdesk_team.xml",
    ],
    "bootstrap": True,
    "assets": {
        "web.assets_frontend": [
            # Front-end libraries
            # ("include", "web._assets_helpers"),
            # ("include", "web._assets_frontend_helpers"),
            # "web/static/src/scss/pre_variables.scss",
            # "web/static/lib/bootstrap/scss/_variables.scss",
            # ("include", "web._assets_bootstrap_frontend"),
            # ("include", "web._assets_bootstrap_backend"),
            # "/web/static/lib/odoo_ui_icons/*",
            # "/web/static/lib/bootstrap/scss/_functions.scss",
            # "/web/static/lib/bootstrap/scss/_mixins.scss",
            # "/web/static/lib/bootstrap/scss/utilities/_api.scss",
            # "web/static/src/libs/fontawesome/css/font-awesome.css",
            # ("include", "web._assets_core"),
            "web/static/src/views/fields/formatters.js",
            # Barcode reader utils
            "web/static/src/webclient/barcode/barcode_scanner.js",
            "web/static/src/webclient/barcode/barcode_scanner.xml",
            "web/static/src/webclient/barcode/barcode_scanner.scss",
            "web/static/src/webclient/barcode/crop_overlay.js",
            "web/static/src/webclient/barcode/crop_overlay.xml",
            "web/static/src/webclient/barcode/crop_overlay.scss",
            "web/static/src/webclient/barcode/ZXingBarcodeDetector.js",
            "barcodes/static/src/components/barcode_scanner.js",
            "barcodes/static/src/components/barcode_scanner.xml",
            "barcodes/static/src/components/barcode_scanner.scss",
            "barcodes/static/src/barcode_service.js",
            # MV Website Helpdesk
            "mv_website_helpdesk/static/src/js/helpdesk_warranty_activation_form.js",
            "mv_website_helpdesk/static/src/components/**/*",
        ],
    },
    "license": "LGPL-3",
    "application": True,
}
