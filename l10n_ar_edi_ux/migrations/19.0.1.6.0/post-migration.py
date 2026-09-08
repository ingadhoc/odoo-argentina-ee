from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Move l10n_ar_edi's l10n_ar_show_withholding_legend into the new
    l10n_ar_invoice_pdf_legend selector, which supersedes it, so that companies already
    printing the withholding legend keep printing it and print it only once.

    TODO 20.0: drop along with the rest of the odoo/enterprise#102032 backport.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.company"]._l10n_ar_migrate_withholding_legend()
