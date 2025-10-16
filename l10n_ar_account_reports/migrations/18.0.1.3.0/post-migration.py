from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Apply report tags to AR companies."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Get all companies with responsibility type code '1'
    companies = env["res.company"].search([("account_fiscal_country_id.code", "=", "AR")])

    # Execute chart template function for these companies
    if companies:
        chart_template = env["account.chart.template"]
        chart_template._l10n_ar_account_reports_setup_account_tags(companies)
