from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _inter_company_prepare_invoice_data(self, invoice_type):
        invoice_vals = super()._inter_company_prepare_invoice_data(invoice_type)
        if self.l10n_latam_use_documents and self.l10n_latam_document_number and self.l10n_latam_document_type_id:
            bill = self.env["account.move"].new(
                {key: invoice_vals[key] for key in ("move_type", "journal_id", "partner_id", "company_id")}
            )
            if (
                bill.l10n_latam_manual_document_number
                and self.l10n_latam_document_type_id in bill.l10n_latam_available_document_type_ids._origin
            ):
                invoice_vals.update(
                    {
                        "l10n_latam_document_type_id": self.l10n_latam_document_type_id.id,
                        "l10n_latam_document_number": self.l10n_latam_document_number,
                    }
                )
        return invoice_vals
