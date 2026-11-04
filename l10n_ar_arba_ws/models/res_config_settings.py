from odoo import _, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ar_arba_env = fields.Selection(
        related="company_id.l10n_ar_arba_env",
        readonly=False,
    )
    l10n_ar_arba_client_id = fields.Char(related="company_id.l10n_ar_arba_client_id", readonly=False)
    l10n_ar_arba_client_secret = fields.Char(related="company_id.l10n_ar_arba_client_secret", readonly=False)
    l10n_ar_arba_wh_mode = fields.Selection(related="company_id.l10n_ar_arba_wh_mode", readonly=False)

    def l10n_ar_arba_test_ws_connection(self):
        self.ensure_one()
        afip_ws = "A122R"
        ws_company = self.company_id._l10n_ar_arba_ws_company()
        arba_env = ws_company.l10n_ar_arba_env
        # Call _l10n_ar_get_token_data directly to bypass _get_environment_type() (AFIP env),
        # which in testing databases always returns 'testing' regardless of the ARBA environment.
        # The ARBA token URL is determined by company.l10n_ar_arba_env, not the AFIP env.
        try:
            self.env["l10n_ar.afipws.connection"]._l10n_ar_get_token_data(self.company_id, afip_ws)
            msg = _(
                "* %(webservice)s: Connection is available (ARBA env: %(arba_env)s)",
                webservice=afip_ws,
                arba_env=arba_env,
            )
            if ws_company != self.company_id:
                msg += "\n" + _("It uses the ARBA credentials of company %s", ws_company.name)
        except UserError as error:
            msg = _("* %(webservice)s: Connection failed. %(message)s", webservice=afip_ws, message=str(error).strip())
        except Exception as error:
            msg = _(
                "* %(webservice)s: Connection failed. This is what we get: %(error)s",
                webservice=afip_ws,
                error=repr(error),
            )
        raise UserError(msg)
