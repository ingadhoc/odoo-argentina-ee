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
    )

    l10n_ar_arba_client_id = fields.Char("Client ID")
    l10n_ar_arba_client_secret = fields.Char("Client Secret")

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

    def _get_arba_environment_type(self):
        """Necesario para agregar luego capa seguridad en bases test/train"""
        return self.l10n_ar_arba_env
