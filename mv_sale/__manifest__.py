# -*- coding: utf-8 -*-
{
    'name': 'MV Sale',
    'description': """
        - Discount Agency
    """,
    'category': '',
    'version': '17.0',
    'author': '',
    'depends': [
        'sale',
        'website_sale_loyalty'
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/mv_discount_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/mv_compute_discount_view.xml',
        'views/mv_compute_discount_line_views.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # 'mv_sale/static/src/js/*.js',
        ],
    },
}
