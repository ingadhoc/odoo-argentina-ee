from odoo import _, models
from odoo.exceptions import UserError


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
        if not amounts_by_account:
            return

        # super() only updated the cache: `amount_currency` is still pending there with the
        # value converted at the company rate. Send it to the database before overwriting the
        # rows by SQL, otherwise the pending write is flushed afterwards and silently discards
        # the amount the user typed.
        opening_move.line_ids.flush_recordset()

        updated_lines = self.env["account.move.line"]
        for account in to_update:
            # Check if this account has an amount_in_currency value stored
            amount_in_currency_value = amounts_by_account.get(account.id)

            # Only process accounts with a specific currency and amount_in_currency set
            if not amount_in_currency_value or not account.currency_id or account.currency_id == self.currency_id:
                continue

            account_lines = opening_move.line_ids.filtered(lambda line: line.account_id == account)
            if len(account_lines) > 1:
                # `amount_in_currency` is a single value per account, so it can only describe
                # one opening line. With a debit and a credit line at the same time there is
                # no way to tell which side the amount belongs to: the value read back would
                # be the two sides netted — an amount the user never typed — and the next
                # save would apply that net over one side, silently dropping what was loaded
                # on it. Ask for the net balance on a single side instead of guessing.
                raise UserError(
                    _(
                        "The account %s has an amount in its own currency, so it can only carry one "
                        "opening balance. Load the net balance on the debit or the credit side, not both.",
                        account.display_name,
                    )
                )
            if not account_lines:
                continue

            # The sign follows the side of the line the amount is applied on, read the same
            # way core does it (`'debit' if line.balance > 0.0 or line.amount_currency > 0.0
            # else 'credit'`, see `_update_opening_move` in account/models/company.py). It is
            # not cosmetic: a credit line left with a positive `amount_currency` is rejected
            # by `account_move_line_check_amount_currency_balance_sign`, and once stored it
            # would be read back as a debit line on the next save, where `update_vals`
            # overwrites or deletes it — which is why the opening credit never stuck.
            final_amount_currency = amount_in_currency_value
            if account_lines.balance < 0.0:
                final_amount_currency = -amount_in_currency_value

            # Update amount_currency directly via SQL to avoid triggering recomputations
            # that could unbalance the move
            self.env.cr.execute(
                "UPDATE account_move_line SET amount_currency = %s WHERE id = %s",
                (final_amount_currency, account_lines.id),
            )
            updated_lines |= account_lines

        if not updated_lines:
            return

        # Drop the cache so the new values are read back from the database. `flush=False` is
        # required: the default flushes the cache first, which would push the stale converted
        # amount over the rows we just updated.
        updated_lines.invalidate_recordset(["amount_currency"], flush=False)
        # The raw UPDATE also bypasses the recomputation of the stored fields that depend on
        # `amount_currency` — `amount_residual`, `amount_residual_currency` and `reconciled`
        # (`_compute_amount_residual`) — which would leave the residual of a receivable or
        # payable opening line out of sync with its amount, and drag that into the
        # reconciliation against the payments. Mark them for recompute: core flushes right
        # after this precommit callback (`_load_precommit_update_opening_move`).
        updated_lines.modified(["amount_currency"])
