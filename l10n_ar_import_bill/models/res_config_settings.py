from odoo import models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def action_import_sales_from_arca(self):
        """Open wizard to import sales from ARCA with counterpart account requirement"""
        # Check if fiscal periods have been set (accounting_start_date must be set)
        if not self.company_id.account_opening_date:
            raise UserError(
                "You must set fiscal periods first before importing sales from ARCA. "
                "Please use 'Set Periods' button to configure your fiscal year."
            )

        return {
            "type": "ir.actions.act_window",
            "name": "Import Sales from ARCA",
            "res_model": "afip.import.file.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_company_id": self.company_id.id,
                "import_type": "sale",
            },
        }

    def action_import_purchases_from_arca(self):
        """Open wizard to import purchases from ARCA with counterpart account requirement"""
        # Check if fiscal periods have been set (accounting_start_date must be set)
        if not self.company_id.account_opening_date:
            raise UserError(
                "You must set fiscal periods first before importing purchases from ARCA. "
                "Please use 'Set Periods' button to configure your fiscal year."
            )

        return {
            "type": "ir.actions.act_window",
            "name": "Import Purchases from ARCA",
            "res_model": "afip.import.file.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_company_id": self.company_id.id,
                "import_type": "purchase",
            },
        }
