from odoo import Command
from odoo.addons.l10n_ar_withholding.tests.test_withholding_ar_ri import TestArWithholdingArRi
from odoo.exceptions import UserError
from odoo.tests import tagged

# A period far from anything the database may already carry
TEST_PERIOD_DATE = "2015-06-10"


@tagged("-at_install", "post_install")
class TestResetToDraft(TestArWithholdingArRi):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dj_model = cls.env["l10n_ar.dj.arba"]
        cls.arba_company = cls.company_ri
        # Batch import: automatic mode would report to ARBA on payment post
        cls.arba_company.write({"l10n_ar_arba_env": "demo", "l10n_ar_arba_wh_mode": "batch_import"})

    def _create_ddjj(self, state, name):
        """Create a DDJJ as ARBA left it, bypassing the webservice."""
        ddjj = self.dj_model.create({"company_id": self.arba_company.id, "date": TEST_PERIOD_DATE})
        ddjj.write({"state": state, "name": name, "open_date": "2015-06-10 10:00:00"})
        return ddjj

    def _create_withholding_line(self, ddjj):
        """Create a supplier payment carrying a withholding already reported in the DDJJ."""
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.res_partner_adhoc.id,
                "company_id": self.arba_company.id,
                "journal_id": self.company_data["default_journal_bank"].id,
                "date": TEST_PERIOD_DATE,
                "amount": 1000.0,
                "l10n_ar_withholding_line_ids": [
                    Command.create({"tax_id": self.tax_wth_test_2.id, "base_amount": 1000.0, "amount": 100.0})
                ],
            }
        )
        line = payment.l10n_ar_withholding_line_ids
        line.write({"l10n_ar_dj_arba_id": ddjj.id, "l10n_ar_cert_number": "2015/00001/00000001"})
        return line

    def test_ddjj_without_withholdings_is_reset_and_deleted(self):
        for state, name in (("open", "900000001"), ("close", "900000002")):
            with self.subTest(state=state):
                ddjj = self._create_ddjj(state, name)
                line = self._create_withholding_line(ddjj)
                # The user unlinks the withholding by hand, e.g. editing the payment in draft
                line.unlink()

                ddjj.action_draft()

                self.assertEqual(ddjj.state, "draft")
                self.assertFalse(ddjj.name, "The ID of a DJ that no longer exists in ARBA must not be kept")
                self.assertFalse(ddjj.open_date)
                ddjj.unlink()
                self.assertFalse(ddjj.exists())

    def test_ddjj_with_withholdings_stays_blocked(self):
        ddjj = self._create_ddjj("open", "900000003")
        self._create_withholding_line(ddjj)

        with self.assertRaisesRegex(UserError, "has withholding lines"):
            ddjj.action_draft()
        self.assertEqual(ddjj.state, "open")
        self.assertEqual(ddjj.name, "900000003")

        with self.assertRaisesRegex(UserError, "draft state"):
            ddjj.unlink()
        self.assertTrue(ddjj.exists())
