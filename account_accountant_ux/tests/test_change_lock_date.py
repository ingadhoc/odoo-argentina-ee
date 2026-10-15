# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestChangeLockDateBypass(AccountTestInvoicingCommon):
    """Regresión (tarea 69068): el parámetro 'account.bypass_lock_date_validation'
    debe permitir mover hacia atrás el Hard Lock Date desde el wizard 'Change Lock Date'.

    Sin el fix, el wizard corta en _prepare_lock_date_values con
    'It is not possible to decrease or remove the Hard Lock Date' antes de llegar
    a res.company.write (donde vive el bypass de _validate_locks).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.older_date = fields.Date.from_string("2016-01-31")
        cls.company.hard_lock_date = fields.Date.from_string("2016-06-30")

    def _wizard(self, hard_lock_date):
        return self.env["account.change.lock.date"].create(
            {
                "company_id": self.company.id,
                "hard_lock_date": hard_lock_date,
            }
        )

    def test_bypass_off_blocks_hard_lock_decrease(self):
        """Sin bypass: mover el hard lock date hacia atrás debe seguir fallando."""
        self.env["ir.config_parameter"].sudo().set_param("account.bypass_lock_date_validation", "False")
        with self.assertRaisesRegex(UserError, "decrease or remove the Hard Lock Date"):
            self._wizard(self.older_date).change_lock_date()

    def test_bypass_on_allows_hard_lock_decrease(self):
        """Con bypass: el wizard debe permitir retroceder el hard lock date."""
        self.env["ir.config_parameter"].sudo().set_param("account.bypass_lock_date_validation", "True")
        self._wizard(self.older_date).change_lock_date()
        self.assertEqual(self.company.hard_lock_date, self.older_date)


@tagged("post_install", "-at_install")
class TestChangeLockDateOtherCompany(AccountTestInvoicingCommon):
    """Regression (ticket 130358): the lock date wizard lets the user pick the company (e.g. a branch), so the
    lock dates must be compared, validated and written against that company and not against the active one.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.branch = cls.env["res.company"].create({"name": "Branch", "parent_id": cls.company.id})
        cls.env.user.company_ids |= cls.branch
        cls.env["account.lock_exception"].search([]).sudo().unlink()

    def _change_lock_date(self, vals):
        wizard = self.env["account.change.lock.date"].create({"company_id": self.branch.id, **vals})
        wizard.change_lock_date()

    def test_set_same_lock_date_as_active_company(self):
        self.company.sudo().fiscalyear_lock_date = "2020-12-31"
        self._change_lock_date({"fiscalyear_lock_date": "2020-12-31"})
        self.assertEqual(self.branch.fiscalyear_lock_date, fields.Date.from_string("2020-12-31"))

    def test_decrease_lock_date_creates_exception_on_selected_company(self):
        self.branch.sudo().sale_lock_date = "2021-01-31"
        self._change_lock_date(
            {"sale_lock_date": "2020-12-31", "exception_applies_to": "everyone", "exception_duration": "1h"}
        )
        self.assertEqual(self.branch.sale_lock_date, fields.Date.from_string("2021-01-31"))
        exception = self.env["account.lock_exception"].search([])
        self.assertRecordValues(
            exception, [{"company_id": self.branch.id, "sale_lock_date": fields.Date.from_string("2020-12-31")}]
        )
        self.assertFalse(self.company.sale_lock_date)

    def test_decrease_lock_date_for_everyone_forever(self):
        self.branch.sudo().sale_lock_date = "2021-01-31"
        self._change_lock_date(
            {"sale_lock_date": "2020-12-31", "exception_applies_to": "everyone", "exception_duration": "forever"}
        )
        self.assertEqual(self.branch.sale_lock_date, fields.Date.from_string("2020-12-31"))
