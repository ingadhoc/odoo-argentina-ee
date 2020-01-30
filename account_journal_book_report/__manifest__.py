# -*- encoding: utf-8 -*-
{
    'name': "Reporte de Libro Diario Contable",
    'version': "12.0.1.1.0",
    'author': "ADHOC SA",
    'website': "www.adhoc.com.ar",
    'category': "Localisation/Accounting",
    'license': "AGPL-3",
    'depends': [
        "account_reports",
        # depends on report_extended instaed of report_aeroo because the first
        # one adds myget/myset functionality
        "report_extended",
    ],
    'data': [
        'wizard/account_journal_book_report_views.xml',
        'report/account_journal_book_report.xml',
        'security/ir.model.access.csv',
        'views/account_views.xml',
        'views/account_journal_book_group_views.xml',
    ],
    'installable': False,
}
