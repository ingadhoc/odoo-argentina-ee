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
