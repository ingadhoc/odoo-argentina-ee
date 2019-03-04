# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'MIS Builder Cash Flow',
    'version': '11.0.1.4.0',
    'license': 'AGPL-3',
    'author': 'ADHOC SA, '
              'Odoo Community Association (OCA)',
    'website': 'https://github.com/OCA/mis-builder',
    'depends': [
        'mis_builder',
        'account_ux',  # for get_model_id_and_name method
    ],
    'data': [
        'security/mis_cash_flow_security.xml',
        'report/mis_cash_flow_views.xml',
        'views/mis_cash_flow_forecast_line_views.xml',
        'views/account_move_line_views.xml',
        'data/mis_report_style.xml',
        'data/mis_report.xml',
        'data/mis_report_instance.xml',
    ],
    'installable': True,
    'maintainers': ['jjscarafia'],
    'development_status': 'Beta',
}
