{
    'name': 'Argentinian Electronic Invoicing UX',
    'version': "17.0.1.4.0",
    'category': 'Localization/Argentina',
    'sequence': 14,
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'summary': '',
    'depends': [
        'l10n_ar_ux',
        'l10n_ar_edi',
        'account_accountant',
    ],
    'external_dependencies': {
        'python': ['zeep'],
    },
    'data': [
        'wizards/res_partner_update_from_padron_wizard_view.xml',
        'wizards/account_check_action_wizard_view.xml',
        'views/res_partner_view.xml',
        'views/account_move_view.xml',
        'views/account_journal_view.xml',
        'views/l10n_ar_boarding_permission_view.xml',
        'views/account_payment_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'demo/res_partner_demo.xml',
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
}
