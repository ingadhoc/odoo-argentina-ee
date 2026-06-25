from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountImportSummary(models.TransientModel):
    _inherit = "account.import.summary"

    account_opening_move_id = fields.Many2one(
        "account.move",
        string="Opening Entry",
        default=lambda self: self.env.company.account_opening_move_id,
        readonly=True,
        help="Entry containing the opening balance of all the company's accounts",
    )

    def action_open_company_data_setup(self):
        return self.env.company._get_records_action(
            name=_("Set your company data"),
            target="new",
        )

    def action_open_fiscal_year_setup(self):
        """Open the fiscal year setup wizard with the current company in context."""
        new_wizard = self.env["account.financial.year.op"].sudo().create({"company_id": self.env.company.id})

        return new_wizard.with_context(dialog_size="medium")._get_records_action(
            target="new",
        )

    def action_open_partner_balance_import(self):
        """Open the partner balance import wizard."""

        if not self.env.company.account_opening_date:
            raise UserError(
                _(
                    "You must set fiscal periods before importing partner balances.\n\n"
                    "Please click 'Set Periods' to configure the opening date and the fiscal periods."
                )
            )

        return (
            self.env["account.balance_import_wizard"]
            .with_context(
                default_mode="partner_balance",
                default_company_id=self.env.company.id,
            )
            ._get_records_action(
                name=_("Import Partner Balance"),
                target="new",
            )
        )

    def action_open_journal_dashboard(self):
        """Open the journal dashboard to review journals."""
        return self.env["ir.actions.act_window"]._for_xml_id("account.open_account_journal_dashboard_kanban")
