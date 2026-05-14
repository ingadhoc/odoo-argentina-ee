from datetime import datetime

from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_backward_replacement_tax(self, tax, date=None):
        """Replace a backward tax with the corresponding partner tax.

        Uses the same logic as _get_settlement_tax from l10n_ar_tax_settlement_backward_comp
        to find the appropriate partner tax for backward taxes.

        :param tax: account.tax record to check and potentially replace
        :param date: Date to use for date range filtering (defaults to order date)
        :return: Replaced tax record or original tax if not backward
        """
        # If not a backward tax, return as is
        if not tax.is_backward_tax:
            return tax

        # If the tax is active, it's already migrated to the new version
        if tax.active:
            return tax

        # En SO siempre son percepciones, no aplica el caso de retenciones
        partner_field = self.order_id.partner_id.l10n_ar_partner_perception_ids

        # Use order date if no date is provided
        date = date or self.order_id.date_order
        # Convert datetime to date for comparison with date fields
        if isinstance(date, datetime):
            date = date.date()

        # Search for matching partner tax with date range and state validation
        partner_tax = partner_field.filtered(
            lambda x: (
                x.company_id == self.company_id
                and x.tax_id.l10n_ar_state_id == tax.l10n_ar_state_id
                and (x.from_date <= date if x.from_date else not x.from_date)
                and (x.to_date >= date if x.to_date else not x.to_date)
            )
        )

        return partner_tax.tax_id if partner_tax else tax

    def _prepare_base_line_for_taxes_computation(self, **kwargs):
        """Override to replace backward taxes with partner taxes before tax computation.

        This method replaces any backward taxes (is_backward_tax=True) with the
        corresponding taxes from the partner configuration, maintaining consistency
        with how invoice taxes are handled in l10n_ar_tax_settlement_backward_comp.
        """
        self.ensure_one()

        # Replace backward taxes with partner taxes
        if self.tax_id:
            kwargs["tax_ids"] = self.tax_id.mapped(lambda tax: self._get_backward_replacement_tax(tax))

        # Call parent with replaced tax_ids
        return super()._prepare_base_line_for_taxes_computation(**kwargs)
