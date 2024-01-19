from odoo import models, fields
from odoo.tools.misc import formatLang


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _get_journal_dashboard_data_batched(self):
        res = super(AccountJournal, self)._get_journal_dashboard_data_batched()
        self._fill_journal_dashboard_general_balance(res)
        return res

    def _fill_journal_dashboard_general_balance(self, dashboard_data):
        journals = self.filtered(lambda journal: journal.type in ['bank', 'cash'])
        for journal in journals:
            if journal.default_account_id:
                amount_field = 'aml.balance' if (not journal.currency_id or journal.currency_id == journal.company_id.currency_id) else 'aml.amount_currency'
                query = """SELECT sum(%s) FROM account_move_line aml
                            LEFT JOIN account_move move ON aml.move_id = move.id
                            WHERE aml.account_id = %%s
                            AND move.date <= %%s AND move.state = 'posted';""" % (amount_field,)
                self.env.cr.execute(query, (journal.default_account_id.id, fields.Date.context_today(self),))
                query_results = self.env.cr.dictfetchall()
                if query_results and query_results[0].get('sum') != None:
                    account_sum = query_results[0].get('sum')
                    currency = journal.currency_id or journal.company_id.currency_id
                    dashboard_data[journal.id].update({
                        'account_balance_general': formatLang(self.env, currency.round(account_sum) + 0.0, currency_obj=currency)
                    })
