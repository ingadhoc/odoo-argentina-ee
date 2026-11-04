from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ar_arba_env = fields.Selection(
        selection=[
            ("demo", "Demo"),
            ("testing", "Testing"),
            ("production", "Production"),
        ],
        default="demo",
        string="ARBA Environment",
        help="A branch with the same CUIT and no CIT of its own uses the environment of the company whose CIT it uses.",
    )

    l10n_ar_arba_client_id = fields.Char(
        "Client ID",
        help="A branch with the same CUIT and no CIT of its own uses the client ID of the company whose CIT it uses.",
    )
    l10n_ar_arba_client_secret = fields.Char(
        "Client Secret",
        help="A branch with the same CUIT and no CIT of its own uses the client secret of the company whose CIT it "
        "uses.",
    )

    # Revisar si necesitamos campo para guardar actividad ARBA
    # posibles valores son
    #     1 RÉGIMEN DE RETEN.EMPRESAS CONSTRUCTORAS
    #     6 RÉGIMEN GENERAL DE RETENCIONES
    #     10 ACTIVIDAD AGROPECUARIA
    #     13 MUNICIPALIDAD
    #     14 ESTADO NACIONAL
    #     15 ESTADO PROVINCIAL
    #     16 SEGUROS
    #     17 FINANCIERAS/BANCOS
    #     20 INSTITUTO PROV.DE LOTERIA Y CASINOS
    #     23 HONORARIOS

    l10n_ar_arba_wh_mode = fields.Selection(
        selection=[
            ("automatic", "Automatic"),
            ("batch_import", "Batch Import"),
        ],
        default="batch_import",
        string="ARBA Withholding Mode",
        help="* Automatic: Withholdings will be automatically reported to ARBA when the payment is confirmed\n* Batch Import: Withholdings must be manually reported to ARBA by clicking the 'Inform to ARBA' button after payment validation",
    )

    def _l10n_ar_arba_ws_company(self):
        """The company whose A122R credentials this one uses, in sudo.

        CIT, client id, client secret and environment go together: a branch without CIT uses
        all of them from the nearest company of its fiscal entity that has a CIT.
        """
        self.ensure_one()
        return self._l10n_ar_get_same_cuit_company_with("arba_cit") or self.sudo()

    def _l10n_ar_get_arba_ws_connection(self):
        """A122R connection, with the credentials of ``_l10n_ar_arba_ws_company``.

        A122R does not use the ARCA certificate, so the connection never goes to the company
        that holds the certificate (``l10n_ar_edi_ux``).
        """
        self.ensure_one()
        return (
            self._l10n_ar_arba_ws_company()
            .with_context(l10n_ar_skip_cert_ancestor=True)
            ._l10n_ar_get_connection("A122R")
        )

    def _get_arba_ws_environment_type(self):
        """Necesario para agregar luego capa seguridad en bases test/train"""
        return self._l10n_ar_arba_ws_company().l10n_ar_arba_env
