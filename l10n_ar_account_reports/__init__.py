##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from . import models


def _post_init_hook_configure_ar_account_tags(env):
    """Configure account tags for existing Argentine companies when installing the module"""
    # Search for companies using Argentine accounting template
    companies = env["res.company"].search([("account_fiscal_country_id.code", "=", "AR")])
    # Apply tags to accounts
    env["account.chart.template"]._l10n_ar_account_reports_setup_account_tags(companies)
