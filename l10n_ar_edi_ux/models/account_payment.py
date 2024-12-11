from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # TO DO: DELETE FROM THIS MODULE IN V18 THE check_add_debit_button FIELD
    check_add_debit_button = fields.Boolean(related='journal_id.check_add_debit_button', readonly=True)
