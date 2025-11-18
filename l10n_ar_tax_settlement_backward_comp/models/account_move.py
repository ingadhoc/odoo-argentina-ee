from odoo import models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def copy(self, default=None):
        res = super().copy(default=default)

        backward_taxes = self.line_ids.mapped('tax_line_id').filtered('is_backward_tax')
        for bw_tax in backward_taxes:
            if bw_tax.active:
                # if its active then is created in new version, so we skip it
                continue

            partner_field = (
                self.partner_id.l10n_ar_partner_perception_ids if self.is_invoice() else self.partner_id.l10n_ar_partner_tax_ids
            )
            tax_line = self.line_ids.filtered(lambda l: l.tax_line_id == bw_tax)

            if partner_tax := partner_field.filtered(
                lambda x: x.company_id == tax_line.company_id
                and x.tax_id.l10n_ar_state_id == tax_line.tax_line_id.l10n_ar_state_id
                and (x.from_date <= tax_line.date if x.from_date else not x.from_date)
                and (x.to_date >= tax_line.date if x.to_date else not x.from_date)
            ):
                for line in res.line_ids.filtered(lambda l: bw_tax in l.tax_ids):
                    # remove backward tax and add partner tax
                    line.tax_ids = [(3, bw_tax.id), (4, partner_tax.tax_id.id)]
            else:
                for line in res.line_ids.filtered(lambda l: bw_tax in l.tax_ids):
                    # just remove backward tax
                    line.tax_ids = [(3, bw_tax.id)]

                res.message_post(
                    body=_(
                        'The backward tax %(tax)s was removed from the copied move '
                        'because there is no corresponding partner tax configured.'
                    ) % {'tax': bw_tax.name},
                    subtype='mail.mt_note',
                )

        return res
