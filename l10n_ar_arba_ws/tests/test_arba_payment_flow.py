from odoo.addons.l10n_ar_tax.tests.common import L10nArTaxPaymentCommon
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestArbaPaymentFlow(L10nArTaxPaymentCommon):
    """A supplier payment with an ARBA withholding, informed in DEMO mode when it is posted."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({"l10n_ar_arba_env": "demo", "l10n_ar_arba_wh_mode": "automatic"})
        cls.tax_arba = cls._create_withholding_tax(
            "Test IIBB BA WTH 3%",
            -3,
            l10n_ar_withholding_tax_type="iibb_untaxed",
            l10n_ar_state_id=cls.env.ref("base.state_ar_b").id,
        )

    def _posted_arba_payment(self):
        bill = self._create_bill(1000.0, "1-1")
        payment = self._create_payment(bill, self.tax_arba)
        line = payment.withholding_line_ids.filtered(lambda x: x.tax_id == self.tax_arba)
        self.assertTrue(line.is_arba_ws_needed)
        return payment, line

    def test_post_informs_the_withholding(self):
        payment, line = self._posted_arba_payment()

        self.assertTrue(line.l10n_ar_cert_number.startswith("Demo-"))
        self.assertEqual(line.name, line.l10n_ar_cert_number)
        # the internal number of the withholding is kept in its reference
        self.assertTrue(line.ref)
        self.assertNotEqual(line.ref, line.name)
        self.assertEqual(line.l10n_ar_dj_arba_id.state, "open")
        self.assertIn(line, line.l10n_ar_dj_arba_id.l10n_ar_withholding_ids)
        self.assertAlmostEqual(line._get_company_currency_amounts()["amount"], 30.0)

    def test_reset_to_draft_warns_and_keeps_the_certificate(self):
        payment, line = self._posted_arba_payment()
        cert_number, internal_number = line.l10n_ar_cert_number, line.ref

        action = payment.action_draft()
        self.assertEqual(action["res_model"], "arba.withholding.draft.warning")
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(wizard.withholding_count, 1)
        self.assertIn(cert_number, wizard.withholding_info)

        wizard.action_confirm_reset_to_draft()
        self.assertEqual(payment.state, "draft")
        self.assertEqual(line.l10n_ar_cert_number, cert_number)
        self.assertEqual(line.name, cert_number)
        self.assertEqual(line.ref, internal_number)

        # posting again does not inform the withholding twice
        payment.action_post()
        self.assertEqual(line.l10n_ar_cert_number, cert_number)
        self.assertEqual(line.name, cert_number)
