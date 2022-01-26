{
    'name': 'Tax Settlement',
    'version': "15.0.1.1.0",
    'category': 'Accounting',
    'sequence': 14,
    'summary': '',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        # por ahora agregamos esta dep para permitir vincular a reportes
        'account_reports',
        # dependencia porque llevamos a pagos y tmb porque usamos el boton
        # en apuntes contables para abrir documento relacionado
        'account_payment_group',
    ],
    'data': [
        'wizards/account_tax_settlement_wizard_view.xml',
        'wizards/get_dates_wizard_view.xml',
        'wizards/download_files_wizard.xml',
        'views/account_move_line_view.xml',
        'views/account_move_view.xml',
        'views/account_journal_view.xml',
        'views/account_journal_dashboard_view.xml',
        'views/account_financial_html_report_line_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
}
