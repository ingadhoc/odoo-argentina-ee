from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = "account.account"

    amount_in_currency = fields.Monetary(
        string="Amount in Account Currency",
        currency_field="company_currency_id",
        compute="_compute_amount_in_currency",
        inverse="_inverse_opening_amount_in_currency",
    )

    @api.depends_context("company")
    def _compute_amount_in_currency(self):
        self.amount_in_currency = 0.0
        opening_move = self.env.company.account_opening_move_id
        if not self.ids or not opening_move:
            return

        opening_lines = self.env["account.move.line"].search(
            [
                ("move_id", "=", opening_move.id),
                ("account_id", "in", self.ids),
            ]
        )
        # One amount per account, so at most one opening line can carry it:
        # `_update_opening_move` rejects loading both sides on an account with an amount in
        # its own currency. Summing is only to avoid keeping whichever line came last on the
        # accounts that predate that check, which made the displayed value depend on the
        # order the lines were read in.
        amount_by_account = defaultdict(float)
        for line in opening_lines:
            amount_by_account[line.account_id.id] += line.amount_currency
        for account in self:
            account.amount_in_currency = amount_by_account.get(account.id, 0.0)

    def _inverse_opening_amount_in_currency(self):
        # Store the amount_in_currency value in precommit data so it can be used
        # by _update_opening_move when the opening_balance/debit/credit is modified.
        # We don't trigger the opening move update here because we need the user
        # to also set the opening_balance (which contains the company currency amount).
        for account in self:
            if account.currency_id and account.currency_id != self.env.company.currency_id:
                # Store in precommit data for later use
                if "account_opening_amount_in_currency" not in self.env.cr.precommit.data:
                    self.env.cr.precommit.data["account_opening_amount_in_currency"] = {}
                data = self.env.cr.precommit.data["account_opening_amount_in_currency"]
                data.setdefault(self.env.company.id, {})[account.id] = account.amount_in_currency

                # Editing only this column has to re-apply the amount too. Core schedules
                # `_load_precommit_update_opening_move` from `_set_opening_debit_credit`, so
                # without a debit/credit write the opening move is never updated and the typed
                # amount is silently dropped. Register the account with the balances it already
                # has, unless a debit/credit write already did it for this same save.
                # Only the sides that carry a balance: a zero would make core delete the
                # corresponding line instead of leaving it alone.
                opening_balances = self.env.cr.precommit.data.get("import_account_opening_balance", {})
                if account.id not in opening_balances.get(self.env.company.id, {}):
                    if account.opening_debit:
                        account._set_opening_debit_credit(account.opening_debit, "debit")
                    if account.opening_credit:
                        account._set_opening_debit_credit(account.opening_credit, "credit")

    @api.model
    def _balance_import_link_by_code(self, fields, data, id_by_code):
        """Give the rows without a database id the one of the account with that code."""
        if "code" not in fields:
            return
        if ".id" not in fields:
            fields.append(".id")
            for row in data:
                row.append(False)
        id_index = fields.index(".id")
        code_index = fields.index("code")
        for row in data:
            if not row[id_index]:
                row[id_index] = id_by_code.get(row[code_index], False)

    @api.model
    def load(self, fields, data):
        """On the balances import from the guide, list the accounts the file would create or
        rename before doing it. The test run shows them; the import is held back until the
        same changes were shown once."""
        if not self.env.context.get("account_balance_import"):
            return super().load(fields, data)

        accounts = self.with_context(active_test=False).search([])
        old_values = {account.id: (account.code, account.name) for account in accounts}
        self._balance_import_link_by_code(
            fields, data, {account.code: account.id for account in accounts if account.code}
        )
        with self.env.cr.savepoint() as savepoint:
            result = super().load(fields, data)
            imported = self.browse(result["ids"] or [])
            new_accounts = imported.filtered(lambda account: account.id not in old_values)
            renamed = imported.filtered(
                lambda account: account.id in old_values and old_values[account.id] != (account.code, account.name)
            )
            keys = sorted(
                {f"new:{account.code or ''}:{account.name}" for account in new_accounts}
                | {f"rename:{account.id}:{account.code}:{account.name}" for account in renamed}
            )
            if not keys:
                return result

            changes = []
            if new_accounts:
                changes.append(_("new accounts: %(accounts)s", accounts=", ".join(new_accounts.mapped("display_name"))))
            if renamed:
                changes.append(
                    _(
                        "renamed accounts: %(accounts)s",
                        accounts=", ".join(
                            "%s %s → %s" % (*old_values[account.id], account.display_name) for account in renamed
                        ),
                    )
                )
            changes = "; ".join(changes)
            if self.env.context.get("account_balance_import_dryrun"):
                message = _(
                    "The import will create or rename accounts (%(changes)s). "
                    "Check that the file is right; if it is, click Import.",
                    changes=changes,
                )
                result["messages"] = result["messages"] + [
                    {"type": "warning", "message": message, "account_keys": keys}
                ]
                return result
            if set(keys) <= set(self.env.context.get("account_balance_announced") or []):
                return result

            savepoint.close(rollback=True)
            message = _(
                "Nothing was imported: the file would create or rename accounts (%(changes)s). "
                "Check that the file is right; if it is, click Import again.",
                changes=changes,
            )
            return {
                "ids": False,
                "messages": [{"type": "error", "message": message, "account_keys": keys}],
                "nextrow": 0,
            }

    @api.constrains("amount_in_currency")
    def _check_amount_in_currency(self):
        for account in self:
            if account.amount_in_currency:
                if not account.currency_id or account.currency_id == self.env.company.currency_id:
                    raise ValidationError(
                        _(
                            "You cannot set an amount in currency "
                            "for accounts that don't have a specific currency defined or use the same currency as the company."
                        )
                    )
