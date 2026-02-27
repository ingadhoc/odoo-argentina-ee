from odoo import Command, models


class FollowupManualReminder(models.TransientModel):
    _inherit = "account_followup.manual_reminder"

    def default_get(self, fields_list):
        """Override to exclude attachments from invoices with no_followup lines."""
        defaults = super().default_get(fields_list)

        if "attachment_ids" in defaults and defaults.get("partner_id"):
            partner = self.env["res.partner"].browse(defaults["partner_id"])

            # Filter out invoices where all receivable/payable lines have no_followup=True
            aml_domain = [
                ("partner_id", "=", partner.id),
                ("reconciled", "=", False),
                ("account_id.account_type", "in", ("asset_receivable", "liability_payable")),
                ("no_followup", "=", False),
            ]
            followup_lines = self.env["account.move.line"].search(aml_domain)
            valid_invoices = followup_lines.mapped("move_id")

            # Update attachment_ids with only valid invoices
            defaults["attachment_ids"] = [Command.set(valid_invoices.message_main_attachment_id.ids)]

        return defaults
