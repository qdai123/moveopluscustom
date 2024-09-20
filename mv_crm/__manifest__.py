# File: __manifest__.py

{
    'name': 'MV CRM',
    'version': '17.0.1.0',
    'summary': 'Custom CRM module extending crm.lead',
    'category': 'Moveoplus/CRM',
    'depends': ['crm', 'mv_base'],
    'data': [
        "views/crm_lead_views.xml",
    ],
    'application': True,
    'license': 'LGPL-3',

}
