from odoo import api, models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Disparamos actualización si alguna de las líneas pertenece a un return
        returns = res.debit_move_id.move_id.closing_return_id | res.credit_move_id.move_id.closing_return_id
        if returns:
            returns._update_payment_state()
        return res

    def unlink(self):
        returns = self.debit_move_id.move_id.closing_return_id | self.credit_move_id.move_id.closing_return_id
        res = super().unlink()
        if returns:
            returns._update_payment_state()
        return res
