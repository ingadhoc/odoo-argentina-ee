from odoo import fields, models


class L10nArPaymentWithholding(models.Model):
    _inherit = "l10n_ar.payment.withholding"

    l10n_ar_cert_number = fields.Char(readonly=True, string="ARBA Withholding Certificate Number")
    l10n_ar_dj_arba_id = fields.Many2one(
        "l10n_ar.dj.arba", "DJ ARBA", help="Declaración Jurada de ARBA asociada a esta retención"
    )
    l10n_ar_arba_wh_mode = fields.Selection(
        related="company_id.l10n_ar_arba_wh_mode",
        string="ARBA Withholding Mode",
    )
    l10n_ar_state_id = fields.Many2one(related="tax_id.l10n_ar_state_id")

    def send_to_arba(self):
        """Send the withholding to ARBA webservice and store the certificate number"""
        for withholding in self.filtered(lambda x: not x.l10n_ar_cert_number):
            withholding.l10n_ar_dj_arba_id._create_withholding(withholding)
