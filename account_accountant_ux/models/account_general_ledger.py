##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountGeneralLedgerHandler(models.AbstractModel):
    _inherit = "account.general.ledger.report.handler"

    def _custom_options_initializer(self, report, options, previous_options):
        """Let the CSV export out of the "select the main company and its branches" gate.

        Every export button of this report ships with ``branch_allowed`` —PDF and XLSX in
        ``account_report._init_options_buttons``, and ours in ``l10n_ar_account_reports``—
        except the CSV one this handler adds (``account_general_ledger``), which was left
        without it. So on a tree with branches the same report exports to XLSX and refuses
        to export to CSV, with an error about the company selector that has nothing to do
        with what the file contains.

        The export is of what the user ticked, and that is a complete answer whatever else
        the tree holds: a partial selection of a legal entity is allowed —what is refused is
        mixing Tax IDs, and that is refused where it means something, not here.
        """
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        for button in options.get("buttons", []):
            if button.get("action_param") == "generate_csv_export":
                button["branch_allowed"] = True
