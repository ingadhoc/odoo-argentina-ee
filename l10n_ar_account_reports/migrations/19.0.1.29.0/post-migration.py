import logging

from odoo import SUPERUSER_ID, Command, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Tag the existing expense_other accounts of AR companies as "AR EERR: Otros Gastos".

    The tag setup only runs on chart load, so these accounts stayed out of the current
    year result, while the prior years earnings now include every profit and loss
    account. Accounts that already have an AR EERR tag are left as they are.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    otros_gastos = env.ref("l10n_ar_account_reports.ar_eerr_otros_gastos", raise_if_not_found=False)
    companies = env["res.company"].search([("account_fiscal_country_id.code", "=", "AR")])
    if not otros_gastos or not companies:
        return
    eerr_tag_ids = (
        env["ir.model.data"]
        .search(
            [
                ("module", "=", "l10n_ar_account_reports"),
                ("model", "=", "account.account.tag"),
                ("name", "=like", "ar_eerr_%"),
            ]
        )
        .mapped("res_id")
    )
    accounts = (
        env["account.account"]
        .with_context(active_test=False)
        .search(
            [
                ("account_type", "=", "expense_other"),
                ("company_ids", "in", companies.ids),
                ("tag_ids", "not in", eerr_tag_ids),
            ]
        )
    )
    accounts.write({"tag_ids": [Command.link(otros_gastos.id)]})
    _logger.info("AR EERR: Otros Gastos tag set on %s expense_other accounts: %s", len(accounts), accounts.ids)
