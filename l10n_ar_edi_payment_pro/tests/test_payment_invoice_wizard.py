from odoo import fields
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestPaymentInvoiceWizard(TestArCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        journal = cls._create_journal("wsfe", data={"l10n_ar_afip_pos_system": "RAW_MAW"})
        cls.origin_invoice = cls._create_invoice_ar(partner_id=cls.res_partner_adhoc)
        payment = cls.env["account.payment"].create(
            {
                "partner_id": cls.res_partner_adhoc.id,
                "partner_type": "customer",
                "payment_type": "inbound",
                "amount": 100,
            }
        )
        cls.wizard = (
            cls.env["account.payment.invoice.wizard"]
            .with_context(active_id=payment.id)
            .create(
                {
                    "payment_id": payment.id,
                    "journal_id": journal.id,
                    "product_id": cls.product_iva_cero.id,
                    "amount_total": 100,
                    "origin_invoice_id": cls.origin_invoice.id,
                }
            )
        )
        cls.today = fields.Date.context_today(cls.wizard)

    def test_notes_from_payment_carry_origin_and_period(self):
        """The note made from a payment points to its origin invoice, and an automatic surcharge
        debit note on an electronic journal gets the associated period ARCA asks for."""
        with self.subTest("a credit note points to the origin invoice"):
            vals = self.wizard.with_context(refund=True).get_invoice_vals()
            self.assertEqual(vals["move_type"], "out_refund")
            self.assertEqual(vals["reversed_entry_id"], self.origin_invoice.id)
            self.assertNotIn("debit_origin_id", vals)

        with self.subTest("an automatic surcharge debit note gets the origin and last month as period"):
            vals = self.wizard.with_context(is_automatic_subcharge=True).get_invoice_vals()
            self.assertEqual(vals["debit_origin_id"], self.origin_invoice.id)
            self.assertNotIn("reversed_entry_id", vals)
            self.assertEqual(vals["l10n_ar_afip_asoc_period_start"], fields.Date.subtract(self.today, months=1))
            self.assertEqual(vals["l10n_ar_afip_asoc_period_end"], self.today)
