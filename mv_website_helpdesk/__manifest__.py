# -*- coding: utf-8 -*-
{
    'name': 'MV Website Helpdesk',
    'version': '17.0.1.0',
    'category': 'Moveoplus/MV Website Helpdesk',
    'description': "Base on Website Helpdesk module to customize new features",
    'author': 'Phat Dang <phat.dangminh@moveoplus.com>',
    'depends': [
        # Odoo
        'barcodes',
        'web',
        # Odoo (Enterprice)
        'website_helpdesk',
        # Moveoplus
        'mv_helpdesk',
    ],
    'data': [
        # SECURITY
        'security/ir.model.access.csv',
        # DATA
        'data/helpdesk_data.xml',
        # VIEWS
        'views/helpdesk_templates.xml',
    ],
    'bootstrap': True,
    'assets': {
        'web.assets_backend': [],
        'mv_website_helpdesk.assets_public_website_helpdesk': [
            # Front-end libraries
            ('include', 'web._assets_helpers'),
            ('include', 'web._assets_frontend_helpers'),
            'web/static/src/scss/pre_variables.scss',
            'web/static/lib/bootstrap/scss/_variables.scss',
            ('include', 'web._assets_bootstrap_frontend'),
            ('include', 'web._assets_bootstrap_backend'),
            '/web/static/lib/odoo_ui_icons/*',
            '/web/static/lib/bootstrap/scss/_functions.scss',
            '/web/static/lib/bootstrap/scss/_mixins.scss',
            '/web/static/lib/bootstrap/scss/utilities/_api.scss',
            'web/static/src/libs/fontawesome/css/font-awesome.css',
            ('include', 'web._assets_core'),

            # Public Kiosk app and its components
            "mv_website_helpdesk/static/src/public_helpdesk_ticket_scanner/**/*",
            'mv_website_helpdesk/static/src/components/**/*',
            "web/static/src/views/fields/formatters.js",

            # Barcode reader utils
            "web/static/src/webclient/barcode/barcode_scanner.js",
            "web/static/src/webclient/barcode/barcode_scanner.xml",
            "web/static/src/webclient/barcode/barcode_scanner.scss",
            "web/static/src/webclient/barcode/crop_overlay.js",
            "web/static/src/webclient/webclient_layout.scss",
            "web/static/src/webclient/barcode/crop_overlay.xml",
            "web/static/src/webclient/barcode/crop_overlay.scss",
            "web/static/src/webclient/barcode/ZXingBarcodeDetector.js",
            "barcodes/static/src/components/barcode_scanner.js",
            "barcodes/static/src/components/barcode_scanner.xml",
            "barcodes/static/src/components/barcode_scanner.scss",
            "barcodes/static/src/barcode_service.js",
        ]
    },
    'license': 'LGPL-3',
    'application': True,
}
