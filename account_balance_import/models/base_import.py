from odoo import fields, models


class BaseImport(models.TransientModel):
    _inherit = "base_import.import"

    account_balance_announced_codes = fields.Json(
        help="Codes of the new accounts already shown to the user on the account balances import"
    )

    def execute_import(self, fields, columns, options, dryrun=False):
        """Remember the new accounts listed to the user, so importing the same file again
        creates them (see `account.account.load`)."""
        if self.res_model != "account.account" or not self.env.context.get("account_balance_import"):
            return super().execute_import(fields, columns, options, dryrun=dryrun)

        announced_codes = self.account_balance_announced_codes or []
        result = super(
            BaseImport,
            self.with_context(
                account_balance_import_dryrun=dryrun,
                account_balance_announced_codes=announced_codes,
            ),
        ).execute_import(fields, columns, options, dryrun=dryrun)
        new_codes = {code for message in result.get("messages", []) for code in message.get("account_codes", [])}
        if new_codes:
            self.account_balance_announced_codes = sorted(new_codes | set(announced_codes))
        return result
