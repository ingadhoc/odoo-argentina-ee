from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def reconcile(self):
        res = super().reconcile()
        # Close an AR loan once every capital instalment is fully reconciled. The
        # native close (account_move._post) keys off generating_loan_line_id, which
        # AR moves never set, so it never fires for this flow.
        # reconcile() runs on every reconciliation in the system, so cheaply skip the
        # search unless a payable line was actually fully reconciled here.
        candidates = self.filtered(lambda l: l.reconciled and l.account_id.account_type == "liability_payable")
        if not candidates:
            return res
        loans = self.env["account.loan.line"].search([("capital_move_line_id", "in", candidates.ids)]).loan_id
        for loan in loans.filtered(lambda l: l.is_ar_loan and l.state == "running"):
            capital_lines = loan.line_ids.filtered(lambda l: not l.is_grace_period)
            if capital_lines and all(line.capital_move_line_id.reconciled for line in capital_lines):
                loan.state = "closed"
        return res
