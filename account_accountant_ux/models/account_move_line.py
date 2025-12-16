from odoo import fields, models


class AccountMovetLine(models.Model):
    _inherit = "account.move.line"

    filter_amount = fields.Float(compute="_compute_filter_amout", search="_search_filter_amount")

    def _compute_filter_amout(self):
        self.filter_amount = False

    def _search_filter_amount(self, operator, value):
        """Search method for same amount filter"""
        preferred_value = self.env.context.get("preferred_aml_value", 0)

        # If users select multiple filters, Odoo combine them using 'in' operator with a set/list of values.
        # So we have to iterate to get the operators of the sub-domains
        if operator == "in" and hasattr(value, "__iter__"):
            # Handle multiple values (orderset, list, tuple)
            domains = []
            for val in value:
                domains.extend(self._get_amount_domain(val, preferred_value))
            return domains
        else:
            # Handle single value
            return self._get_amount_domain(value, preferred_value)

    def _get_amount_domain(self, value, preferred_value):
        """Helper method to get domain for a single value"""
        # if journal has currency, search by amount in that currency
        if self.env.context.get("preferred_aml_currency_id") != self.env.company.currency_id.id:
            search_field = "amount_residual_currency"
        else:
            search_field = "amount_residual"

        if value == 1.0:  # "same_amount" filter
            if self.env.context.get("preferred_aml_currency_id") != self.env.company.currency_id.id:
                return [(search_field, "=", preferred_value)]
            return [(search_field, "=", preferred_value)]
        elif value == 2.0:  # "close_amount" filter
            return [
                "&",
                (search_field, ">=", preferred_value - 100),
                (search_field, "<=", preferred_value + 100),
            ]
        elif value == 3.0:  # "less_amount" filter
            return [(search_field, "<", preferred_value)]
        return []
