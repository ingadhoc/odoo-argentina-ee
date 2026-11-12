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
        cls.payment = payment
        wizard_vals = {
            "payment_id": payment.id,
            "journal_id": journal.id,
            "product_id": cls.product_iva_cero.id,
            "amount_total": 100,
        }
        wizard = cls.env["account.payment.invoice.wizard"].with_context(active_id=payment.id)
        cls.wizard = wizard.create({**wizard_vals, "origin_invoice_id": cls.origin_invoice.id})
        cls.wizard_without_origin = wizard.create(wizard_vals)
        cls.today = fields.Date.context_today(cls.wizard)

    def test_notes_from_payment_carry_origin_and_period(self):
        """The note made from a payment points to its origin invoice, and an automatic surcharge
        debit note on an electronic journal gets the associated period ARCA asks for."""
        with self.subTest("a credit note points to the origin invoice"):
            vals = self.wizard.with_context(refund=True).get_invoice_vals()
            self.assertEqual(vals["move_type"], "out_refund")
            self.assertEqual(vals["reversed_entry_id"], self.origin_invoice.id)
            self.assertNotIn("debit_origin_id", vals)

        with self.subTest("an automatic surcharge debit note gets last month as period, with or without origin"):
            vals = self.wizard.with_context(is_automatic_subcharge=True).get_invoice_vals()
            self.assertEqual(vals["debit_origin_id"], self.origin_invoice.id)
            self.assertNotIn("reversed_entry_id", vals)
            # the surcharge debit note is made without an origin invoice
            vals_without_origin = self.wizard_without_origin.with_context(
                is_automatic_subcharge=True
            ).get_invoice_vals()
            self.assertFalse(vals_without_origin["debit_origin_id"])
            for note_vals in (vals, vals_without_origin):
                self.assertEqual(
                    note_vals["l10n_ar_afip_asoc_period_start"], fields.Date.subtract(self.today, months=1)
                )
                self.assertEqual(note_vals["l10n_ar_afip_asoc_period_end"], self.today)
