from odoo import _, fields, models
from odoo.addons.base_import.models.base_import import FIELDS_RECURSION_LIMIT


class BaseImport(models.TransientModel):
    _inherit = "base_import.import"

    account_balance_announced = fields.Json(
        help="New and renamed accounts already shown to the user on the account balances import"
    )

    def get_fields_tree(self, model, depth=FIELDS_RECURSION_LIMIT):
        """Offer the database id as a column on the chart of accounts, so the `.id` column of
        the balances template is matched. Core only offers it on relational subfields. It goes
        by model and not by context because `parse_preview` is called without the action one."""
        fields_tree = super().get_fields_tree(model, depth=depth)
        if model == "account.account" and depth:
            fields_tree.insert(
                1,
                {
                    "id": ".id",
                    "name": ".id",
                    "string": _("Database ID"),
                    "required": False,
                    "fields": [],
                    "type": "id",
                    "model_name": model,
                    "translate": False,
                },
            )
        return fields_tree

    def execute_import(self, fields, columns, options, dryrun=False):
        """Remember the account changes listed to the user, so importing the same file again
        applies them (see `account.account.load`)."""
        if self.res_model != "account.account" or not self.env.context.get("account_balance_import"):
            return super().execute_import(fields, columns, options, dryrun=dryrun)

        announced = self.account_balance_announced or []
        result = super(
            BaseImport,
            self.with_context(
                account_balance_import_dryrun=dryrun,
                account_balance_announced=announced,
            ),
        ).execute_import(fields, columns, options, dryrun=dryrun)
        keys = {key for message in result.get("messages", []) for key in message.get("account_keys", [])}
        if keys:
            self.account_balance_announced = sorted(keys | set(announced))
        return result
