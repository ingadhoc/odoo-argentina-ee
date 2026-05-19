import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Apply new account tags to AR companies after patrimonio_neto tag migration.

    This migration applies the new specific account tags (ar_esp_capital,
    ar_esp_reservas, ar_esp_resultados) to all accounts in Argentine companies.
    The pre-migration script has already removed the old ar_esp_patrimonio_neto
    tag relationships to avoid conflicts.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    companies = env["res.company"].search([("account_fiscal_country_id.code", "=", "AR")])

    if companies:
        chart_template = env["account.chart.template"]
        chart_template._l10n_ar_account_reports_setup_account_tags(companies)
        _logger.info("✓ Account tags applied successfully")
