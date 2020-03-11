{
    'name': 'Argentinian Electronic Invoicing UX',
    'version': "13.0.1.0.0",
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
        'views/res_partner_view.xml',
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
