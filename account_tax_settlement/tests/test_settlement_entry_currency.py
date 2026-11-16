from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSettlementEntryCurrency(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_currency = cls.setup_other_currency("EUR")
        cls.journal = cls.company_data["default_journal_misc"]
        cls.counterpart_account = cls.company_data["default_account_revenue"]

    def _create_account(self, currency):
        return self.env["account.account"].create(
            {
                "name": "Settled account",
                "code": "SETTLED%s" % currency.name,
                "account_type": "asset_current",
                "currency_id": currency.id,
            }
        )

    def _settle_entry(self, account, balance, amount_currency):
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.journal.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": account.id,
                            "currency_id": account.currency_id.id,
                            "debit": balance,
                            "amount_currency": amount_currency,
                        },
                    ),
                    (0, 0, {"account_id": self.counterpart_account.id, "credit": balance}),
                ],
            }
        )
        entry.action_post()
        lines_vals = self.journal._get_tax_settlement_entry_lines_vals([("move_id", "=", entry.id)])
        settlement = self.env["account.move"].create(self.journal._get_tax_settlement_entry_vals(lines_vals))
        settlement.action_post()
        return settlement.line_ids.filtered(lambda line: line.account_id == account)

    def test_settle_account_in_company_currency(self):
        """An account whose currency is the company one must be settled without unbalancing the entry"""
        account = self._create_account(self.env.company.currency_id)
        line = self._settle_entry(account, 1000.0, 1000.0)
        self.assertRecordValues(
            line, [{"credit": 1000.0, "amount_currency": -1000.0, "currency_id": self.env.company.currency_id.id}]
        )

    def test_settle_account_in_foreign_currency(self):
        """An account in a foreign currency must be settled in both the company and the foreign currency"""
        account = self._create_account(self.other_currency)
        line = self._settle_entry(account, 1000.0, 2000.0)
        self.assertRecordValues(
            line, [{"credit": 1000.0, "amount_currency": -2000.0, "currency_id": self.other_currency.id}]
        )
