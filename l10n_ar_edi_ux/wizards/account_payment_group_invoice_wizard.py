from odoo import fields, models


class AccountPaymentGroupInvoiceWizard(models.TransientModel):
    _inherit = "account.payment.group.invoice.wizard"

    l10n_ar_afip_asoc_period_start = fields.Date(
        'Associate Period From',
    )
    l10n_ar_afip_asoc_period_end = fields.Date(
        'Associate Period To',
    )
    origin_invoice_id = fields.Many2one(
        'account.move',
    )
    commercial_partner_id = fields.Many2one(
        'res.partner',
        related="payment_group_id.partner_id.commercial_partner_id"
    )

    def get_invoice_vals(self):
        self.ensure_one()
        invoice_vals = super().get_invoice_vals()
        origin_doc = "reversed_entry_id" if invoice_vals['type'] in ['in_refund', 'out_refund'] else "debit_origin_id"
        invoice_vals.update({
            'l10n_ar_afip_asoc_period_start': self.l10n_ar_afip_asoc_period_start,
            'l10n_ar_afip_asoc_period_end': self.l10n_ar_afip_asoc_period_end,
            origin_doc: self.origin_invoice_id
        })
        return invoice_vals
