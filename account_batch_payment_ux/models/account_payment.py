from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def unlink(self):
        if self.batch_payment_id:
            self.batch_payment_id.verify_unlinked_payments_from_batch()
        res = super().unlink()
        return res

    def _get_batch_matched_statement_lines(self):
        lines = self.reconciled_statement_line_ids
        aml = self.env["account.move.line"]
        # Payments without move are matched via payment_lines_ids (account_accountant_batch_payment)
        if "payment_lines_ids" in aml._fields:
            lines |= aml.search([("payment_lines_ids", "in", self.ids)]).move_id.statement_line_id
        return lines
