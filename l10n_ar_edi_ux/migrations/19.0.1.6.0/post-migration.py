from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Copy l10n_ar_edi's l10n_ar_show_withholding_legend into the new
    l10n_ar_invoice_pdf_legend_ux selector, which supersedes it, so that companies already
    printing the withholding legend keep printing it and no other company starts printing
    it. The boolean is left as it is: printing the legend once is guaranteed by replacing
    the report block of l10n_ar_edi, not by the value of the data.

    TODO 20.0: drop along with the rest of the odoo/enterprise#102032 backport.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.company"]._l10n_ar_migrate_withholding_legend()
