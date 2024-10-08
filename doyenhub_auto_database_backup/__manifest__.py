# -*- coding: utf-8 -*-

{
    'name': 'Auto Database Backup',
    'version': '1.0.0',
    'category': 'Database Backup',
    'author': 'Doyenhub Software Solution',
    'company': 'Doyenhub Software Solution',
    'maintainer': 'Doyenhub Software Solution',
    'sequence': -100,
    'summary': 'Auto Database Backup Tool',
    'description': """Auto Database Backup Tool""",
    'depends': ['base','mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/menu.xml',
        ],
    'demo': [],
    'images': ['static/description/banner.png'],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
    'assets': {},
    'website':'https://moveoauto.com.vn/',
}
