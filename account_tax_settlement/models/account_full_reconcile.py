from odoo import api, models


class AccountFullReconcile(models.Model):
    _inherit = "account.full.reconcile"

    @api.model_create_multi
    def create(self, vals_list):
        fulls = super().create(vals_list)
        fulls.mapped("reconciled_line_ids").filtered("move_id.settled_line_ids").mapped(
            "move_id.settled_line_ids"
        )._compute_tax_state()
        return fulls

    def unlink(self):
        settlement_lines = (
            self.mapped("reconciled_line_ids").filtered("move_id.settled_line_ids").mapped("move_id.settled_line_ids")
        )
        res = super().unlink()
        settlement_lines._compute_tax_state()
        return res
