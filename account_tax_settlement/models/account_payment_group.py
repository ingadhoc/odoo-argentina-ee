from odoo import models


class AccountPaymentGroup(models.Model):

    _inherit = 'account.payment.group'

    def _get_to_pay_move_lines_domain(self):
        to_pay_move_line_ids = self._context.get('to_pay_move_line_ids', [])
        if to_pay_move_line_ids:
            return [
                ('id', 'in', to_pay_move_line_ids),
            ]
        return super()._get_to_pay_move_lines_domain()
