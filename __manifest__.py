# -*- coding: utf-8 -*-
{
    'name': "myhotel",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'product', 'sale_stock', 'point_of_sale'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'views/myhotel.xml',
        'views/reservation.xml',
        'views/client.xml',
        'views/sequence.xml',
        'views/email.xml',
        'views/room_summ_view.xml',
        'views/room_res.xml',
        'views/facture.xml',

    ],

    'qweb': ['static/src/xml/hotel_room_summary.xml'],

    'installable': True,
    'auto_install': False,
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
        'demo/hotel_scheduler.xml',
    ],
}