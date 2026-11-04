# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import date

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestBalanceSheetEarnings(AccountTestInvoicingCommon):
    """Prior years earnings only keep what the current year result does not show.

    The current year result sums by AR EERR tag and the prior years line by account
    type, so every profit and loss account type has to be in both.
    """

    @classmethod
    @AccountTestInvoicingCommon.setup_chart_template("ar_ri")
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.year = fields.Date.today().year
        cls.other_expense_account = cls.env["account.account"].create(
            {
                "name": "Otros gastos (test)",
                "code": "5.9.9.99.001",
                "account_type": "expense_other",
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.env["account.chart.template"]._l10n_ar_account_reports_setup_account_tags(cls.company, only_missing=True)
        cls.report = cls.env.ref("l10n_ar_account_reports.account_financial_report_l10n_ar_estado_patrimonial")

    def _post_other_expense(self, move_date, amount):
        move = self.env["account.move"].create(
            {
                "date": move_date,
                "journal_id": self.company_data["default_journal_misc"].id,
                "line_ids": [
                    (0, 0, {"account_id": self.other_expense_account.id, "debit": amount}),
                    (0, 0, {"account_id": self.company_data["default_account_assets"].id, "credit": amount}),
                ],
            }
        )
        move.action_post()

    def _earnings(self):
        options = self.report.get_options(
            {
                "date": {
                    "date_from": "%s-01-01" % self.year,
                    "date_to": "%s-12-31" % self.year,
                    "mode": "single",
                    "filter": "custom",
                },
                "unfold_all": True,
            }
        )
        codes = {
            line.id: line.code
            for line in self.report.line_ids
            if line.code in ("ar_curr_year_earnings", "ar_prev_year_earnings")
        }
        earnings = {}
        for line in self.report._get_lines(options):
            # Line ids carry their parents' ids; the report line comes before its unfolded children.
            code = codes.get(self.report._get_res_id_from_line_id(line["id"], "account.report.line"))
            if code and code not in earnings:
                earnings[code] = line["columns"][0]["no_format"]
        return earnings

    def test_other_expense_account_gets_eerr_tag(self):
        self.assertIn(self.env.ref("l10n_ar_account_reports.ar_eerr_otros_gastos"), self.other_expense_account.tag_ids)

    def test_other_expenses_split_between_current_and_prior_years(self):
        self._post_other_expense(date(self.year - 1, 6, 1), 1000.0)
        self._post_other_expense(date(self.year, 6, 1), 300.0)
        earnings = self._earnings()
        self.assertAlmostEqual(earnings["ar_curr_year_earnings"], -300.0)
        self.assertAlmostEqual(earnings["ar_prev_year_earnings"], -1000.0)
