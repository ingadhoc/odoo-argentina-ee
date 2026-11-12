from odoo import fields
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import Form, tagged


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

    def _wizard_form(self, journal, refund=True, document_type=None):
        context = {"active_id": self.payment.id}
        context.update({"refund": True} if refund else {"internal_type": "debit_note"})
        form = Form(self.env["account.payment.invoice.wizard"].with_context(**context))
        form.journal_id = journal
        form.product_id = self.product_iva_cero
        form.amount_total = 100
        if document_type:
            form.journal_document_type_id = document_type
        return form

    def _assert_period_required(self, form, required):
        if required:
            with self.assertRaisesRegex(AssertionError, "l10n_ar_afip_asoc_period_start is a required field"):
                form.save()
        else:
            form.save()

    def test_associated_period_is_required_where_arca_asks_for_it(self):
        """The period is required for a credit or debit note of the domestic electronic web service (wsfe) with no
        origin invoice, which is what l10n_ar_edi asks for when it posts the note."""
        wsfe = self._create_journal("wsfe", data={"l10n_ar_afip_pos_system": "RAW_MAW"})
        wsfex = self._create_journal("wsfex")
        wsbfe = self._create_journal("wsbfe")
        preprinted = self._create_journal("wsfe", data={"l10n_ar_afip_pos_system": "II_IM"})

        with self.subTest("a wsfe credit note without origin"):
            self._assert_period_required(self._wizard_form(wsfe), True)
        with self.subTest("a wsfe debit note without origin"):
            self._assert_period_required(self._wizard_form(wsfe, refund=False), True)
        with self.subTest("a wsfe credit note with origin"):
            form = self._wizard_form(wsfe)
            form.origin_invoice_id = self.origin_invoice
            self._assert_period_required(form, False)
        with self.subTest("a wsfe document that is not a note"):
            invoice_type = self.env.ref("l10n_ar.dc_a_f")
            self._assert_period_required(self._wizard_form(wsfe, refund=False, document_type=invoice_type), False)
        with self.subTest("export and fiscal bond journals do not send the period"):
            self._assert_period_required(self._wizard_form(wsfex), False)
            self._assert_period_required(self._wizard_form(wsbfe), False)
        with self.subTest("a non electronic journal"):
            self._assert_period_required(self._wizard_form(preprinted), False)
