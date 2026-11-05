from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def unlink(self):
        if self.batch_payment_id:
            self.batch_payment_id.verify_unlinked_payments_from_batch()
        res = super().unlink()
        return res

    def _get_batch_matched_statement_lines(self):
        # Payments without move are matched via payment_lines_ids
        aml = self.env["account.move.line"].search([("payment_lines_ids", "in", self.ids)])
        return self.reconciled_statement_line_ids | aml.move_id.statement_line_id
