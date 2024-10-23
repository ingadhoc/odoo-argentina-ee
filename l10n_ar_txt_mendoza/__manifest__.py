{
    'name': 'TXT Mendoza',
    'version': "16.0.1.0.0",
    'category': 'Accounting',
    'author': 'ADHOC SA',
    'depends': [
        'l10n_ar_ux',
        'purchase',
    ],
    'data': [
        'views/account_move_views.xml',
        'views/afip_activity_view.xml',
        'views/account_payment_view.xml',
        'wizard/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
