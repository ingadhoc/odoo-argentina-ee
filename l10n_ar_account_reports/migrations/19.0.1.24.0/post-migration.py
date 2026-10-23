import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Create the "Sire" withholding tax groups on existing AR companies."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].search([("account_fiscal_country_id.code", "=", "AR")])
    env["account.chart.template"]._l10n_ar_setup_sire_tax_group(companies)
    _logger.info("Sire tax groups set up on %s AR companies", len(companies))
