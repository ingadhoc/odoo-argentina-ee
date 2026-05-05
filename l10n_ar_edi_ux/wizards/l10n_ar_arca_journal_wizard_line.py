# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class L10nArArcaJournalWizardLine(models.TransientModel):
    _name = "l10n_ar.arca.journal.wizard.line"
    _description = "ARCA Journal Wizard Line"
    _order = "afip_ws, pos_number"

    wizard_id = fields.Many2one("l10n_ar.arca.journal.wizard", required=True, ondelete="cascade")

    afip_ws = fields.Selection(
        [
            ("wsfe", "WSFE"),
            ("wsfex", "WSFEX"),
            ("wsbfe", "WSBFE"),
        ],
        string="Web Service",
        required=True,
    )

    afip_ws_name = fields.Char(string="WS Type")

    pos_number = fields.Integer(string="POS Number", required=True)

    pos_system = fields.Selection(selection="_get_pos_system_selection", string="ARCA POS System", required=True)

    name = fields.Char(string="Journal Name", required=True)

    to_create = fields.Boolean(string="Create", default=True)

    branch_id = fields.Many2one(
        "res.company",
        string="Branch",
        domain="[('id', 'child_of', company_id), ('id', '!=', company_id)]",
        help="Select a branch to assign this journal to a specific branch. Leave empty for the main company.",
    )

    shared_to_branches = fields.Boolean(
        string="Shared to Branches", help="If checked, this journal will be shared with all branches."
    )

    company_id = fields.Many2one(related="wizard_id.company_id", store=True)

    error_message = fields.Char(string="Error", readonly=True)

    def _get_pos_system_selection(self):
        """Get POS system selection from account.journal"""
        return self.env["account.journal"]._get_l10n_ar_afip_pos_types_selection()
