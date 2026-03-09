from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ar_arba_env = fields.Selection(
        related="company_id.l10n_ar_arba_env",
        readonly=False,
    )
    l10n_ar_arba_client_id = fields.Char(related="company_id.l10n_ar_arba_client_id", readonly=False)
    l10n_ar_arba_client_secret = fields.Char(related="company_id.l10n_ar_arba_client_secret", readonly=False)
    l10n_ar_arba_wh_mode = fields.Selection(related="company_id.l10n_ar_arba_wh_mode", readonly=False)
