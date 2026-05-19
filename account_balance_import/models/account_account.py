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
        amount_by_account = {line.account_id.id: abs(line.amount_currency) for line in opening_lines}
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
