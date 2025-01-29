{
    'name': 'Tax settlement Mendoza',
    'version': "16.0.1.0.0",
    'category': 'Accounting',
    'author': 'ADHOC SA',
    'license': 'LGPL-3',
    'depends': [
        'l10n_ar_account_tax_settlement',
        'l10n_ar_withholding_ux',
        #'base_import_match',
    ],
    'data': [
        'views/account_move_views.xml',
        'views/afip_activity_view.xml',
        'views/account_payment_view.xml',
        'wizard/res_config_settings_views.xml',
    ],
    'installable': False,
    'auto_install': False,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
