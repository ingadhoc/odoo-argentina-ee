{
    'name': 'Txt SIRE',
    'version': "16.0.1.0.0",
    'category': 'Accounting',
    'website': 'www.adhoc.com.ar',
    'license': 'LGPL-3',
    'depends': [
        'l10n_ar_account_tax_settlement',
    ],
    'data': [
        'data/account_account_tag_data.xml',
        'views/res_partner_view.xml',
        'views/account_payment_view.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
