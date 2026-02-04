from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Apply report tags to AR companies after removing old patrimonio_neto tag."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].search([("account_fiscal_country_id.code", "=", "AR")])

    if companies:
        chart_template = env["account.chart.template"]
        chart_template._l10n_ar_account_reports_setup_account_tags(companies)
