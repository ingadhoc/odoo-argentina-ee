from odoo import models
from odoo.exceptions import UserError


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def _add_move_line_to_statement_line_move(self, vals_list):
        """If reconcile on company_currency is disabled → keep Odoo's native behavior, including
        the creation of exchange difference entries if applicable.

        If reconcile on company_currency is enabled:
            - Forbid mixing accounts with different secondary currencies.
            - When no secondary currency is involved, force disabling exchange difference.
            - When exactly one secondary currency is involved, also disable exchange difference
              to keep consistency with the widget behavior."""

        self.ensure_one()

        # If the company does not enforce company-currency reconciliation,
        # or partner's receivable/payable use a different currency → default behavior.
        if not self.company_id.reconcile_on_company_currency:
            return super()._add_move_line_to_statement_line_move(vals_list)

        # Exceptions with reconcile on company currency active:
        # Journal bank/cash has a different currency than company currency.
        comp_currency = self.env.company.currency_id
        journal_currency = self.journal_id.currency_id
        if journal_currency and journal_currency != comp_currency:
            # Temporarily disable reconcile_on_company_currency for this execution
            return super(
                AccountBankStatementLine,
                self.with_context(disable_reconcile_on_company_currency=True),
            )._add_move_line_to_statement_line_move(vals_list)

        # Collect currencies involved in the move lines.
        Account = self.env["account.account"]
        currencies = []
        for vals in vals_list:
            account_id = vals.get("account_id")
            if not account_id:
                continue
            currency = Account.browse(account_id).currency_id or False
            if currency not in currencies:
                currencies.append(currency)

        # Multiple secondary currencies are forbidden.
        if len(currencies) > 1:
            raise UserError(
                "You cannot reconcile move lines from different secondary currencies "
                "when 'Reconcile On Company Currency' is enabled."
            )

        # Disable exchange difference creation (no secondary currency or exactly one).
        return super(
            AccountBankStatementLine,
            self.with_context(no_exchange_difference_no_recursive=True),
        )._add_move_line_to_statement_line_move(vals_list)
