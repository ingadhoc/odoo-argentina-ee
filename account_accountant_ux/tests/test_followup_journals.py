from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFollowupJournals(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hidden_journal = cls.company_data["default_journal_sale"].copy({"name": "Hidden", "code": "HIDE"})

    def _filter_journals(self, xmlid):
        report = self.env.ref(xmlid)
        options = {"companies": [{"id": self.env.company.id}]}
        return report._get_filter_journals(options)

    def test_partner_balance_reports_ignore_journal_search_filter(self):
        journal_cls = type(self.env["account.journal"])
        origin_search = journal_cls._search
        hidden_id = self.hidden_journal.id

        # Mimic a module that hides journals from _search for regular users (e.g. account_multi_store)
        def _search(records, domain, *args, **kwargs):
            if not records.env.su:
                domain = [*domain, ("id", "!=", hidden_id)]
            return origin_search(records, domain, *args, **kwargs)

        with patch.object(journal_cls, "_search", _search):
            for xmlid in ("account_reports.followup_report", "account_reports.customer_statement_report"):
                journals = self._filter_journals(xmlid)
                self.assertIn(hidden_id, journals.ids, xmlid)
                self.assertFalse(journals.env.su, xmlid)
            self.assertNotIn(hidden_id, self._filter_journals("account_reports.general_ledger_report").ids)
