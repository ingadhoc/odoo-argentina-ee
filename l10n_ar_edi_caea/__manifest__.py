{
    'name' : 'Argentinean EDI CAEA (Asynchronous invoicing)',
    'version' : '1.0',
    'license': 'LGPL-3',
    'summary': '',
    'sequence': 90,
    'category': 'Localizations',
    'website': 'https://www.adhoc.com.ar',
    'depends' : ['l10n_ar_edi'],
    'data': [
        'data/ir_cron_data_data.xml',
        'views/l10n_ar_caea_views.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'demo/account_journal_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
