##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class L10nArUnlinkedTaxSettlement(models.Model):
    _name = "l10n_ar.unlinked.tax.settlement"
    _description = "Withholding Unlinked From Its Tax Settlement"

    move_id = fields.Many2one(
        "account.move",
        "Entry",
        required=True,
        ondelete="cascade",
        index=True,
        help="Entry whose withholding journal item was re-created and lost the link to its settlement.",
    )
    tax_id = fields.Many2one("account.tax", "Withholding Tax", required=True, ondelete="cascade")
    settlement_move_id = fields.Many2one(
        "account.move",
        "Tax Settlement",
        required=True,
        ondelete="cascade",
        help="Settlement where the withholding was declared. The record is dropped with the settlement "
        "because there is nothing left to restore then.",
    )

    _sql_constraints = [
        ("uniq_move_tax", "unique(move_id, tax_id)", "There can only be one unlinked settlement per entry and tax.")
    ]
