from odoo import models


class AccountImportSummary(models.TransientModel):
    _inherit = "account.import.summary"

    def action_open_check_balance_import(self):
        """Open the check balance import wizard."""
        return (
            self.env["account.balance_import_wizard"]
            .with_context(
                default_mode="check_balance",
                default_company_id=self.env.company.id,
            )
            ._get_records_action(
                name="Import Checks",
                target="new",
            )
        )
