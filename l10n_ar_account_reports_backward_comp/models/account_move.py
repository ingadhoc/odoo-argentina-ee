from odoo import _, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def copy(self, default=None):
        res = super().copy(default=default)
        # para facturas que se duplican y:
        # a) venian de la versión anterior
        # b) y no tenian fp o la fp no tenía "percepciones argentinas"
        # c) tiene impuestos con "is_backward_tax" archivados
        # re-calculamos pa percepción desde partner tax
        for rec in self.filtered(lambda m: m.is_sale_document() and m.country_code == "AR"):
            backward_taxes = rec.line_ids.mapped("tax_line_id").filtered("is_backward_tax")
            for bw_tax in backward_taxes:
                if bw_tax.active:
                    # if its active then is created in new version, so we skip it
                    continue

                partner_field = rec.partner_id.l10n_ar_partner_perception_ids
                tax_line = rec.line_ids.filtered(lambda l: l.tax_line_id == bw_tax)[:1]

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
                        "The backward tax '%(tax_name)s (id: %(tax_id)s)' was removed from the copied move "
                        "because there is no corresponding partner tax configured."
                    )
                    % {"tax_name": bw_tax.name, "tax_id": bw_tax.id},
                )

        return res
