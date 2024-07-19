from odoo import api, fields, models


class l10nArPaymentWithholding(models.Model):
    _inherit = "l10n_ar.payment.withholding"

    sire_aplica_cdi = fields.Boolean(
        readonly=False, help="Campo para archivo txt Ganancias SIRE. Marcar si aplica CDI", store=True
    )
    sire_aplica_acrecentamiento = fields.Boolean(
        readonly=False, help="Campo para archivo txt Ganancias SIRE. Marcar si aplica CDI", store=True
    )
    sire_codigo_alicuota = fields.Char(readonly=False, size=4, store=True)
    es_sire = fields.Boolean(store=True)

    @api.onchange("partner_id", "tax_withholding_id")
    def _compute_sire_fields(self):
        """
        This method is triggered when the partner or tax withholding is changed.
        It computes the SIRE fields based on the partner's properties.
        """
        tag_tax_sire = self.env["account.account.tag"].search(
            [("name", "=", "Sire"), ("applicability", "=", "taxes"), ("country_id", "=", self.env.ref("base.ar").id)]
        )
        sire_payments = self.filtered(
            lambda pay: tag_tax_sire in pay.tax_withholding_id.invoice_repartition_line_ids.tag_ids
        )
        for payment in sire_payments:
            payment.es_sire = True
            payment.sire_aplica_cdi = payment.partner_id.sire_aplica_cdi
            payment.sire_aplica_acrecentamiento = payment.partner_id.sire_aplica_acrecentamiento
            payment.sire_codigo_alicuota = payment.partner_id.sire_codigo_alicuota
        for payment in self - sire_payments:
            payment.es_sire = False
            payment.sire_aplica_cdi = False
            payment.sire_aplica_acrecentamiento = False
            payment.sire_codigo_alicuota = ""
