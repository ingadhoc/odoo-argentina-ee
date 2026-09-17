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
    journal_ids = fields.Many2many(
        "account.journal",
        relation="l10n_ar_tax_settlement_reassign_journal_rel",
        compute="_compute_journal_ids",
    )
    candidate_move_ids = fields.Many2many(
        "account.move",
        relation="l10n_ar_tax_settlement_reassign_candidate_rel",
        compute="_compute_candidate_move_ids",
        help="Settlements left with a gap, offered as the most likely ones.",
    )
    settlement_move_id = fields.Many2one(
        "account.move",
        string="Settlement",
        required=True,
        compute="_compute_settlement_move_id",
        store=True,
        precompute=True,
        readonly=False,
        domain="[('journal_id', 'in', journal_ids), ('state', '=', 'posted')]",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends("line_ids")
    def _compute_journal_ids(self):
        for rec in self:
            journals = self.env["account.journal"]
            for line in rec.line_ids:
                journals |= line._get_tax_settlement_journal()
            rec.journal_ids = journals

    @api.depends("line_ids")
    def _compute_candidate_move_ids(self):
        for rec in self:
            candidates = self.env["account.move"]
            # The settlements of a journal are the same for every line of the same date: read them once
            settlements_cache = {}
            for line in rec.line_ids:
                key = (line._get_tax_settlement_journal(), line.date)
                if key not in settlements_cache:
                    settlements_cache[key] = line._get_journal_tax_settlements(date_from=line.date)
                candidates |= line._get_tax_settlement_reassign_candidates(settlements_cache[key])
            rec.candidate_move_ids = candidates

    @api.depends("line_ids")
    def _compute_settlement_move_id(self):
        for rec in self:
            guesses = {line._get_tax_settlement_to_reassign() for line in rec.line_ids}
            rec.settlement_move_id = guesses.pop() if len(guesses) == 1 else False

    def action_reassign(self):
        self.ensure_one()
        return self.line_ids.reassign_tax_settlement(self.settlement_move_id)
