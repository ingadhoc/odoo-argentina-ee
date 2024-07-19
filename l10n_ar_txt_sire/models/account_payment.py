from odoo import models, fields, api


class AccountPayment(models.Model):

    _inherit = "account.payment"

    sire_aplica_cdi = fields.Boolean(related='partner_id.sire_aplica_cdi',
                                     readonly=False,
                                     help="Campo para archivo txt Ganancias SIRE. Marcar si aplica CDI")
    sire_aplica_acrecentamiento = fields.Boolean(related='partner_id.sire_aplica_acrecentamiento',
                                                 readonly=False,
                                                 help="Campo para archivo txt Ganancias SIRE. Marcar si aplica CDI")
    sire_codigo_alicuota = fields.Char(related='partner_id.sire_codigo_alicuota', readonly=False, size=4)
    # Este campo se usa para hacer invisibles los campos anteriores en el pago si no se trata de una retención
    # de sire
    es_sire = fields.Boolean(compute='_compute_es_sire')

    @api.onchange('tax_withholding_id')
    def _compute_es_sire(self):
        tag_tax_sire = self.env.ref('l10n_ar_txt_sire.tag_tax_sire')
        payments_with_sire = self.filtered(lambda pay: tag_tax_sire in
                                           pay.tax_withholding_id.invoice_repartition_line_ids.tag_ids)
        payments_with_sire.es_sire = True
        (self - payments_with_sire).es_sire = False
