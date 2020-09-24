# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Meta Inventory Work 2',
    'version': '1.1.1',
    'category': 'Inventory',
    'sequence': 1,
    'summary': 'Inventory Adjustment Chassis Number Engine Number',
    'description': "",
    'website': 'https://metamorphosis.com.bd/',
    'author': 'Metamorphosis',
    'depends': ['base', 'stock', 'account'],
    'data': [
        'views/stock_production_lot_chassis_engine_view.xml',
        'views/stock_move_line_view.xml',

        'reports/deliveryslip_report.xml',
        # 'reports/inherit_report_invoice.xml',
        'data/sequence_lot.xml',
    ],
    'demo': [

    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
