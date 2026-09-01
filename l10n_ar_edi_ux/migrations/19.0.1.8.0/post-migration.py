from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Copy l10n_ar_show_withholding_legend into the selector that supersedes it.
    See res.company._l10n_ar_migrate_withholding_legend(). TODO 20.0: drop."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.company"]._l10n_ar_migrate_withholding_legend()
