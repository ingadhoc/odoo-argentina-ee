import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Switch the SIRE return type from monthly to fortnightly on existing AR companies.

    deadline_periodicity is company dependent and was filled with the old monthly
    default. Companies that already have SIRE returns are left as they are, because
    changing the periodicity deletes their open returns.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    return_type = env.ref("l10n_ar_account_reports.sire_return_type", raise_if_not_found=False)
    if not return_type:
        return
    companies_with_returns = (
        env["account.return"].with_context(active_test=False).search([("type_id", "=", return_type.id)]).company_id
    )
    return_type = return_type.with_context(tracking_disable=True)
    for company in env["res.company"].search([("account_fiscal_country_id.code", "=", "AR")]):
        company_return_type = return_type.with_company(company)
        if company_return_type.deadline_periodicity != "monthly":
            continue
        if company in companies_with_returns:
            _logger.info("SIRE return type kept monthly on company %s: it already has SIRE returns", company.id)
            continue
        company_return_type.deadline_periodicity = "fortnightly"
        _logger.info("SIRE return type set to fortnightly on company %s", company.id)
