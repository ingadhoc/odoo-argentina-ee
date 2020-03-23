##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def action_general_ledger(self):
        params = {}
        if self.default_debit_account_id and self.default_debit_account_id == \
                self.default_credit_account_id:
            params['id'] = self.default_credit_account_id.id
        return self.env['account.report'].open_general_ledger(
            {}, params=params)
