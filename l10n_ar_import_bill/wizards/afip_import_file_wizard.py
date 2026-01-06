# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class AfipImportFileWizard(models.TransientModel):
    _name = "afip.import.file.wizard"
    _description = "Upload AFIP Excel File"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    available_journal_ids = fields.Many2many(
        "account.journal",
        compute="_compute_available_journals",
        string="Available Journals",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        required=True,
        domain="[('id', 'in', available_journal_ids)]",
    )
    file_data = fields.Binary(string="Archivo ARCA Excel", required=True, help="Archivo Excel exportado desde ARCA")
    file_name = fields.Char(string="Nombre del Archivo")
    counterpart_account_id = fields.Many2one(
        "account.account",
        string="Counterpart Account",
        required=True,
        help="Account used as counterpart when importing from settings",
        domain="[('company_ids','=', company_id), ('active', '=', True)]",
    )

    @api.depends("company_id")
    def _compute_available_journals(self):
        """Compute available journals based on company and context import_type"""
        for wizard in self:
            import_type = self.env.context.get("import_type", [])
            if wizard.company_id and import_type:
                journals = self.env["account.journal"].search(
                    [
                        ("company_id", "=", wizard.company_id.id),
                        ("type", "in", import_type),
                        ("l10n_ar_is_pos", "=", False),
                    ]
                )
                wizard.available_journal_ids = journals
            else:
                wizard.available_journal_ids = False

    def default_get(self, fields_list):
        """Set default values"""
        res = super().default_get(fields_list)

        # Ensure company_id is set
        if not res.get("company_id"):
            res["company_id"] = self.env.company.id

        journal_type = self.env.context.get("import_type")
        # Get first general journal
        journal = self.env["account.journal"].search(
            [("type", "=", journal_type), ("company_id", "=", res["company_id"])], limit=1
        )
        if journal:
            res["journal_id"] = journal.id
        # Get default counterpart account
        res["counterpart_account_id"] = self.env.company.get_unaffected_earnings_account().id

        return res

    def action_process_file(self):
        """Process the uploaded file and open the main import wizard"""
        if not self.file_data:
            raise UserError("Please upload an Excel file to import.")

        # Create a temporary attachment
        attachment = self.env["ir.attachment"].create(
            {
                "name": self.file_name or "import.xlsx",
                "datas": self.file_data,
            }
        )

        try:
            # Use the journal's import method to process the file
            result = self.journal_id.import_bills_from_xls([attachment])

            if result and result.get("res_id"):
                # Get the wizard that was created
                wizard = self.env["afip.import.wizard"].browse(result["res_id"])

                # Set the counterpart account
                wizard.write({"counterpart_account_id": self.counterpart_account_id.id})

                # Return the action to open the main wizard with context
                return {
                    "name": "Importación de Facturas de Cliente",
                    "type": "ir.actions.act_window",
                    "res_model": "afip.import.wizard",
                    "target": "new",
                    "views": [[self.env.ref("l10n_ar_import_bill.view_afip_import_wizard_form").id, "form"]],
                    "res_id": wizard.id,
                    "context": {
                        "from_settings": True,
                        "require_counterpart_account": True,
                        "default_journal_id": self.journal_id.id,
                    },
                }
        finally:
            # Clean up the temporary attachment
            attachment.unlink()
