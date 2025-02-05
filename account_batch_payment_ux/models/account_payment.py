from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def unlink(self):
        if self.batch_payment_id:
            self.batch_payment_id.verify_unlinked_payments_from_batch()
        res = super().unlink()
        return res
