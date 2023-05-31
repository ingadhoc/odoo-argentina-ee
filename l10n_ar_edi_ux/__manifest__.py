{
    'name': 'Argentinian Electronic Invoicing UX',
<<<<<<< HEAD
    'version': "16.0.1.1.0",
||||||| parent of 79dcf4c (temp)
    'version': "15.0.1.2.0",
=======
    'version': "15.0.1.3.0",
>>>>>>> 79dcf4c (temp)
    'category': 'Localization/Argentina',
    'sequence': 14,
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'summary': '',
    'depends': [
        'l10n_ar_ux',
        'l10n_ar_edi',
    ],
    'external_dependencies': {
        'python': ['zeep'],
    },
    'data': [
        'wizards/res_config_settings_view.xml',
        'wizards/res_partner_update_from_padron_wizard_view.xml',
        'wizards/account_payment_group_invoice_wizard_view.xml',
        'views/res_partner_view.xml',
        'views/account_move_view.xml',
        'views/account_journal_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'demo/res_partner_demo.xml',
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
