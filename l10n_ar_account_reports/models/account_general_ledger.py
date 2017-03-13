# -*- coding: utf-8 -*-
from openerp import models


class report_account_general_ledger(models.AbstractModel):
    _inherit = "account.general.ledger"

    def group_by_account_id(self, line_id):
        accounts = super(
            report_account_general_ledger, self).group_by_account_id(line_id)
        only_accounts = self._context.get('only_accounts')
        if only_accounts:
            return {x: accounts[x] for x in only_accounts if accounts.get(x)}
        return accounts
