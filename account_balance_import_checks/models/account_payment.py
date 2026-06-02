from odoo import api, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.model
    def _get_valid_payment_account_types(self):
        account_types = super()._get_valid_payment_account_types()
        if self:
            account_types = self._add_check_account_types(account_types)
        return account_types

    def _add_check_account_types(self, account_types):
        for company in self.mapped("company_id"):
            check = self.l10n_latam_new_check_ids
            if (
                check
                and len(check) == 1
                and any(
                    line.account_id.id in company.get_unaffected_earnings_account().ids
                    for line in self.move_id.line_ids
                )
            ):
                account_types.append("equity_unaffected")

        return account_types
