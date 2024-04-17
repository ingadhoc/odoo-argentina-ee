from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    check_add_debit_button = fields.Boolean(related='journal_id.check_add_debit_button', readonly=True)
