from odoo import SUPERUSER_ID, api


def uninstall_hook(env_or_cr, registry=None):
    if hasattr(env_or_cr, "cr"):
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})

    imd = env["ir.model.data"].search(
        [
            ("module", "=", "l10n_ar_arba_ws"),
            ("name", "=", "l10n_ar_pba_report_pba_withholdings_line_a122r"),
            ("model", "=", "account.report.line"),
        ]
    )
    env["account.report.line"].browse(imd.mapped("res_id")).unlink()
    imd.unlink()
