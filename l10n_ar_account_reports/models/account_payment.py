##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    unlinked_tax_settlement_line_ids = fields.Many2many(
        "account.move.line",
        string="Withholdings To Reassign",
        compute="_compute_unlinked_tax_settlement_line_ids",
        help="Withholdings of this payment that were declared in a tax settlement and are no longer linked to it.",
    )
    unlinked_tax_settlement_count = fields.Integer(compute="_compute_unlinked_tax_settlement_line_ids")

    @api.depends("move_id.unlinked_tax_settlement_ids.settlement_move_id", "move_id.line_ids.tax_settlement_move_id")
    def _compute_unlinked_tax_settlement_line_ids(self):
        for rec in self:
            lines = rec._get_unlinked_tax_settlement_lines()
            rec.unlinked_tax_settlement_line_ids = lines
            rec.unlinked_tax_settlement_count = len(lines)

    def _get_unlinked_tax_settlement_lines(self):
        """Withholding journal items of this payment waiting to be linked back to their settlement.

        A withholding settled again by hand needs no warning, so we only keep the ones still unlinked.
        """
        self.ensure_one()
        pending_taxes = self.move_id.unlinked_tax_settlement_ids.tax_id
        if not pending_taxes:
            return self.env["account.move.line"]
        return self.move_id.line_ids.filtered(lambda x: x.tax_line_id in pending_taxes and not x.tax_settlement_move_id)

    def action_reassign_tax_settlement(self):
        """Link the withholdings back to the settlement kept on the entry when they were re-created."""
        self.ensure_one()
        lines = self._get_unlinked_tax_settlement_lines()
        if not lines:
            raise UserError(_("This payment has no withholdings pending reassignment."))
        for line in lines:
            line.reassign_tax_settlement(line._get_unlinked_tax_settlement_log().settlement_move_id)
        return lines._get_tax_settlement_reassign_notification()

    def action_view_unlinked_tax_settlement_lines(self):
        self.ensure_one()
        return {
            "name": _("Withholdings To Reassign"),
            "type": "ir.actions.act_window",
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": [("id", "in", self.unlinked_tax_settlement_line_ids.ids)],
        }
