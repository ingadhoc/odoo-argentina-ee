##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models


class L10nArTaxSettlementReassign(models.TransientModel):
    _name = "l10n_ar.tax.settlement.reassign"
    _description = "Reassign Tax Settlement"

    line_ids = fields.Many2many("account.move.line", string="Withholdings", required=True)
    line_count = fields.Integer(compute="_compute_line_count")
    candidate_move_ids = fields.Many2many(
        "account.move",
        relation="l10n_ar_tax_settlement_reassign_candidate_rel",
        compute="_compute_candidate_move_ids",
    )
    settlement_move_id = fields.Many2one(
        "account.move",
        string="Settlement",
        required=True,
        domain="[('id', 'in', candidate_move_ids)]",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends("line_ids")
    def _compute_candidate_move_ids(self):
        for rec in self:
            candidates = self.env["account.move"]
            for line in rec.line_ids:
                candidates |= line._get_tax_settlement_reassign_candidates()
            rec.candidate_move_ids = candidates

    def action_reassign(self):
        self.ensure_one()
        return self.line_ids.reassign_tax_settlement(self.settlement_move_id)
