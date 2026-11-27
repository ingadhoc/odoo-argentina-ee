from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def copy(self, default=None):
        res = super().copy(default=default)
        # para facturas que se duplican y:
        # a) venian de la versión anterior
        # b) y no tenian fp o la fp no tenía "percepciones argentinas"
        # c) tiene impuestos con "is_backward_tax" archivados
        # re-calculamos pa percepción desde partner tax
        for rec, new in zip(self, res):
            if not (rec.is_sale_document() and rec.country_code == "AR"):
                continue
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
                    for line in new.line_ids.filtered(lambda l: bw_tax in l.tax_ids):
                        # remove backward tax and add partner tax
                        line.tax_ids = [(3, bw_tax.id), (4, partner_tax.tax_id.id)]
                else:
                    for line in new.line_ids.filtered(lambda l: bw_tax in l.tax_ids):
                        # just remove backward tax
                        line.tax_ids = [(3, bw_tax.id)]
                new.message_post(
                    body=_(
                        "The backward tax '%(tax_name)s (id: %(tax_id)s)' was removed from the copied move "
                        "because there is no corresponding partner tax configured."
                    )
                    % {"tax_name": bw_tax.name, "tax_id": bw_tax.id},
                )

        # archived backward taxes not handled above are removed, as account_ux does for the rest
        for new in res:
            for line in new.line_ids.filtered(lambda l: any(t.is_backward_tax and not t.active for t in l.tax_ids)):
                line.tax_ids = [(3, t.id) for t in line.tax_ids.filtered(lambda t: t.is_backward_tax and not t.active)]
        return res

    def _get_archived_taxes_to_remove_on_copy(self, taxes):
        to_remove = super()._get_archived_taxes_to_remove_on_copy(taxes)
        if self.is_sale_document() and self.country_code == "AR":
            # copy() replaces the archived backward taxes with the partner tax, so they must reach it
            to_remove = to_remove.filtered(lambda x: not x.is_backward_tax)
        return to_remove

    def _is_backward_perception(self, tax):
        return (
            tax.is_backward_tax
            and not tax.active
            and tax.type_tax_use == "sale"
            and tax.l10n_ar_tribute_afip_code == "07"
        )

    def _get_backward_perception_replacement_tax(self, tax):
        """Replace an archived backward IIBB perception with the partner tax of the same jurisdiction."""
        if not (self._is_backward_perception(tax) and tax.l10n_ar_state_id):
            return tax
        date = self.invoice_date or self.date or fields.Date.context_today(self)
        company_domain = self.env["l10n_ar.partner.tax"]._check_company_domain(self.company_id)
        partner_tax = (
            self.commercial_partner_id.l10n_ar_partner_perception_ids.filtered_domain(company_domain)
            .filtered(
                lambda x: (
                    x.tax_id.active
                    and x.tax_id.type_tax_use == tax.type_tax_use
                    and x.tax_id.l10n_ar_tribute_afip_code == "07"
                    and x.tax_id.l10n_ar_state_id == tax.l10n_ar_state_id
                    and (not x.from_date or x.from_date <= date)
                    and (not x.to_date or x.to_date >= date)
                )
            )
            .sorted(lambda x: x.from_date or fields.Date.from_string("1900-01-01"), reverse=True)[:1]
        )
        return partner_tax.tax_id or tax

    def _l10n_ar_get_amounts(self, base_lines=None):
        self.ensure_one()
        if self.state != "draft" and self.is_sale_document(include_receipts=True) and self.country_code == "AR":
            lines = base_lines if base_lines is not None else self._get_rounded_base_and_tax_lines()[0]
            taxes = lines and lines[0]["tax_ids"].browse().union(*(line["tax_ids"] for line in lines))
            if taxes and any(self._is_backward_perception(tax) for tax in taxes):
                replacements = {tax: self._get_backward_perception_replacement_tax(tax) for tax in taxes}
                replaced_lines = [
                    {**line, "tax_ids": line["tax_ids"].browse().union(*(replacements[tax] for tax in line["tax_ids"]))}
                    for line in lines
                ]
                AccountTax = self.env["account.tax"]
                AccountTax._add_tax_details_in_base_lines(replaced_lines, self.company_id)
                tax_amls = self.line_ids.filtered("tax_repartition_line_id")
                tax_lines = [self._prepare_tax_line_for_taxes_computation(tax_line) for tax_line in tax_amls]
                AccountTax._round_base_lines_tax_details(replaced_lines, self.company_id, tax_lines=tax_lines)
                base_lines = replaced_lines
        return super()._l10n_ar_get_amounts(base_lines=base_lines)
