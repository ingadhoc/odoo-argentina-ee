# -*- encoding: utf-8 -*-
{
    'name': "Reporte de Libro Diario Contable",
    'version': "13.0.1.0.0",
    'author': "ADHOC SA",
    'website': "www.adhoc.com.ar",
    'category': "Localisation/Accounting",
    'license': "AGPL-3",
    'depends': [
        "account_reports",
        "report_aeroo",
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
