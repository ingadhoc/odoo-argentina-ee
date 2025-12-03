from odoo import fields, models
from odoo.tools.misc import formatLang


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _get_journal_dashboard_data_batched(self):
        res = super(AccountJournal, self)._get_journal_dashboard_data_batched()
        self._fill_journal_dashboard_general_balance(res)
        return res

    def _fill_journal_dashboard_general_balance(self, dashboard_data):
        journals = self.filtered(
            lambda journal: journal.type in ("bank", "cash", "credit") and journal.default_account_id
        )
        if account_ids := journals.mapped("default_account_id").ids:
            query = """SELECT account_id, sum(balance) as balance, sum(amount_currency) as amount_currency
                            FROM account_move_line
                            WHERE account_id in %(ids)s
                            AND date <= %(date)s AND parent_state = 'posted'
                            GROUP BY account_id"""
            self.env.cr.execute(
                query,
                {
                    "ids": tuple(account_ids),
                    "date": fields.Date.context_today(self),
                },
            )
            query_results = {x["account_id"]: (x["balance"], x["amount_currency"]) for x in self.env.cr.dictfetchall()}

            for journal in journals:
                if query_results and journal.default_account_id.id in query_results:
                    if not journal.currency_id or journal.currency_id == journal.company_id.currency_id:
                        account_sum = query_results[journal.default_account_id.id][0]
                    else:
                        account_sum = query_results[journal.default_account_id.id][1]
                    currency = journal.currency_id or journal.company_id.currency_id
                    dashboard_data[journal.id].update(
                        {
                            "account_balance_general": formatLang(
                                self.env, currency.round(account_sum) + 0.0, currency_obj=currency
                            )
                        }
                    )
