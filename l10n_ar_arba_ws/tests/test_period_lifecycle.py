from odoo import fields
from odoo.tests import tagged

from .common import TEST_PERIOD_DATE, L10nArArbaWsCommon


@tagged("-at_install", "post_install")
class TestPeriodLifecycle(L10nArArbaWsCommon):
    """Task 71519: a cancelled DDJJ must not hold the period hostage.

    Once ARBA no longer knows the declaration, the company has to be able to open a
    fresh one for the same fortnight and keep reporting withholdings.
    """

    def test_cancelled_ddjj_frees_the_period(self):
        period_date = fields.Date.from_string(TEST_PERIOD_DATE)
        cancelled = self._create_ddjj(state="cancel", name=self._next_arba_id())

        with self.subTest("a new withholding opens a fresh DDJJ instead of reusing the cancelled one"):
            reopened = self.dj_model._ensure_dj(period_date, self.arba_company)
            self.assertNotEqual(
                reopened, cancelled, "the cancelled DDJJ was reused, so the period stays blocked forever"
            )
            self.assertEqual(reopened.state, "open")

        with self.subTest("the cancelled and the new DDJJ coexist in the same period"):
            self.assertEqual(self._period_ddjj(), cancelled | reopened)

        with self.subTest("a second cancelled DDJJ of the same period is accepted"):
            second = self._create_ddjj(state="cancel")
            self.assertEqual(self._period_ddjj(), cancelled | reopened | second)

    def _period_ddjj(self):
        """Every DDJJ of the company for the period under test."""
        from_date, to_date = self.dj_model._find_dates(fields.Date.from_string(TEST_PERIOD_DATE))
        return self.dj_model.search(
            [("company_id", "=", self.arba_company.id), ("date", ">=", from_date), ("date", "<=", to_date)]
        )
