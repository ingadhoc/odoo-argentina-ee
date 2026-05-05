##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, models
from odoo.exceptions import UserError


class AccountImportSummary(models.TransientModel):
    _inherit = "account.import.summary"

    def action_open_arca_connection_setup(self):
        """Open the ARCA connection setup wizard for Argentinian companies."""
        if self.env.company.country_id.code != "AR":
            raise UserError(_("This option is only available for Argentinian companies."))
        return self.env.ref("l10n_ar_edi_ux.action_l10n_ar_arca_connection_wizard").read()[0]

    def action_open_arca_journal_wizard(self):
        """Open the ARCA journal creation wizard for Argentinian companies."""
        if self.env.company.country_id.code != "AR":
            return self.action_open_journal_dashboard()
        return self.env.ref("l10n_ar_edi_ux.action_l10n_ar_arca_journal_wizard").read()[0]
