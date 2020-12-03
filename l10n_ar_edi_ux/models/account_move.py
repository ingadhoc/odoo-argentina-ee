from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = "account.move"

    def _found_related_invoice(self):
        """
        TODO borrar cuando se mezcle https://github.com/odoo/enterprise/pull/12972/files
        """
        res = super()._found_related_invoice()
        if not res and self.l10n_latam_document_type_id.internal_type in ['credit_note', 'debit_note'] and \
           self.sudo().env.ref('base.module_sale').state == 'installed':
            original_entry = self.mapped('invoice_line_ids.sale_line_ids.invoice_lines').filtered(
                lambda x:  x.move_id.l10n_latam_document_type_id.country_id.code == 'AR' and
                x.move_id.l10n_latam_document_type_id.internal_type != self.l10n_latam_document_type_id.internal_type
                and x.move_id.l10n_ar_afip_result in ['A', 'O'] and x.move_id.l10n_ar_afip_auth_code).mapped('move_id')
            return original_entry and original_entry[0] or res
        return res
