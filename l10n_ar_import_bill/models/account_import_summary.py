from odoo import models
from odoo.exceptions import UserError


class AccountImportSummary(models.TransientModel):
    _inherit = "account.import.summary"

    def action_import_sales_from_arca(self):
        """Open wizard to import sales from ARCA with counterpart account requirement"""
        # Check if fiscal periods have been set (accounting_start_date must be set)
        if not self.env.company.account_opening_date:
            raise UserError(
                "You must set fiscal periods first before importing sales from ARCA. "
                "Please use 'Set Periods' button to configure your fiscal year."
            )

        return (
            self.env["afip.import.wizard"]
            .with_context(default_company_id=self.env.company.id, import_type="sale")
            ._get_records_action(
                name="Import Sales from ARCA",
                target="new",
                views=[(self.env.ref("l10n_ar_import_bill.view_afip_import_file_wizard_form").id, "form")],
            )
        )

    def action_import_purchases_from_arca(self):
        """Open wizard to import purchases from ARCA with counterpart account requirement"""
        # Check if fiscal periods have been set (accounting_start_date must be set)
        if not self.env.company.account_opening_date:
            raise UserError(
                "You must set fiscal periods first before importing purchases from ARCA. "
                "Please use 'Set Periods' button to configure your fiscal year."
            )
        return (
            self.env["afip.import.wizard"]
            .with_context(default_company_id=self.env.company.id, import_type="purchase")
            ._get_records_action(
                name="Import Purchases from ARCA",
                target="new",
                views=[(self.env.ref("l10n_ar_import_bill.view_afip_import_file_wizard_form").id, "form")],
            )
        )
