{
    'name' : 'Argentinean EDI CAEA (Asynchronous invoicing)',
    'version' : '1.0',
    'license': 'LGPL-3',
    'summary': '',
    'author': 'ADHOC SA, Filoquin',
    'sequence': 90,
    'category': 'Localizations',
    'website': 'https://www.adhoc.com.ar',
    'depends' : ['l10n_ar_edi'],
    'data': [
        'data/ir_cron_data.xml',
        'data/ir_actions_server_data.xml',
        'views/l10n_ar_caea_views.xml',
        'views/account_move_views.xml',
        'views/account_journal_views.xml',
        'views/res_config_settings_views.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'demo/account_journal_views.xml',
    ],
    'installable': True,
}
