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
        origin_doc = "reversed_entry_id" if invoice_vals['move_type'] in ['in_refund', 'out_refund'] else "debit_origin_id"
        invoice_vals.update({
            'l10n_ar_afip_asoc_period_start': self.l10n_ar_afip_asoc_period_start,
            'l10n_ar_afip_asoc_period_end': self.l10n_ar_afip_asoc_period_end,
            origin_doc: self.origin_invoice_id
        })

        # Si estamos creando una ND automatica con el modulo de  account_payment_group_financial_surcharge entonces
        # seteamos automaticamente los campos l10n_ar_afip_asoc_period_start / l10n_ar_afip_asoc_period_end que son
        # necesarios para poder validar la ND electronica automatica. El periodo lo seteamos conforme a la fecha del
        # dia que se esta validando el recibo de pago. Fecha Hasta  (dicha fecha) Fecha Desde (dicha fecha - 1 mes)
        if self.env.context.get('is_automatic_subcharge'):
            journal = self.env['account.journal'].browse(invoice_vals.get('journal_id'))
            if journal.l10n_ar_afip_ws:  # Si soy diario electronico
                period_date = fields.Date.context_today(self)
                invoice_vals.update({
                    'l10n_ar_afip_asoc_period_start': fields.Date().subtract(period_date, months=1),
                    'l10n_ar_afip_asoc_period_end': period_date,
                })

        return invoice_vals
