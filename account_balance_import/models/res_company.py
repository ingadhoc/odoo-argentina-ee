from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _update_opening_move(self, to_update):
        """Call super to perform the normal opening move update, then override
        `amount_currency` on the opening move lines for accounts where an explicit
        value was provided. This avoids fully replacing the core implementation.
        """
        super()._update_opening_move(to_update)
        opening_move = self.account_opening_move_id
        if not opening_move:
            return

        # Get the stored amount_in_currency values from precommit data
        amount_in_currency_data = self.env.cr.precommit.data.get("account_opening_amount_in_currency", {})
        amounts_by_account = amount_in_currency_data.get(self.id, {})

        for account, values in to_update.items():
            # Check if this account has an amount_in_currency value stored
            amount_in_currency_value = amounts_by_account.get(account.id)

            # Only process accounts with a specific currency and amount_in_currency set
            if account.currency_id and amount_in_currency_value and account.currency_id != self.currency_id:
                # Find the opening lines for this account
                opening_lines = opening_move.line_ids.filtered(lambda l: l.account_id == account)
                debit_amount, credit_amount = values[0], values[1]

                # Determine the sign based on whether it's debit or credit
                if debit_amount is not None and debit_amount != 0:
                    final_amount_currency = amount_in_currency_value
                elif credit_amount is not None and credit_amount != 0:
                    final_amount_currency = -amount_in_currency_value
                else:
                    continue

                # Update amount_currency directly via SQL to avoid triggering recomputations
                # that could unbalance the move
                for line in opening_lines:
                    self.env.cr.execute(
                        "UPDATE account_move_line SET amount_currency = %s WHERE id = %s",
                        (final_amount_currency, line.id),
                    )

        # Invalidate cache to ensure the changes are reflected
        if opening_move:
            opening_move.line_ids.invalidate_recordset(["amount_currency"])
