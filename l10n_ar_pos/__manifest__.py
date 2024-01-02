# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Argentinian Point of Sale',
    'version': "1.0",
    'description': "Adapt the Point of Sale to Argentinean localization.",
    'author': 'ADHOC SA, Ing. Gabriela Rivero',
    'category': 'Localization',
    'depends': [
        'l10n_ar_edi',
        'point_of_sale',
    ],
    'data': [
        'views/assets_backend.xml',
        'views/pos_config.xml',
    ],
    'demo': [
    ],
    'qweb': [
        'static/src/xml/pos.xml',
        'static/src/xml/xml_receipt.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
