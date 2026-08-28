from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged

from .common import TestWsmtxcaCommon


@tagged("post_install", "post_install_l10n", "-at_install", *TestWsmtxcaCommon.extra_tags)
class TestWsmtxcaItems(TestWsmtxcaCommon):
    """arrayItems is where the letter of the invoice, the discounts and the
    negative lines all land on the same amounts. That is where wsmtxca rejects."""

    def _invoice_with_discounted_line(self, partner):
        """One line, 2 units at 100 with a 25% discount, plus a section and a note."""
        return self._create_invoice_ar(
            partner_id=partner,
            invoice_line_ids=[
                Command.create({"display_type": "line_section", "name": "Section that carries no amount"}),
                self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=100.0, quantity=2, discount=25.0),
                Command.create({"display_type": "line_note", "name": "Note that carries no amount"}),
            ],
        )

    def test_wsmtxca_items_letter_a_and_b(self):
        """Task 68095: letter A reports the net unit price with the VAT apart,
        letter B reports the unit price with the VAT inside; both land on the
        same importeItem, and neither turns a section or a note into an item.

        Covers behaviours 14, 15, 16 and 20 of the survey.
        """
        # Same economics under both letters: 2 x 100 with 25% off is 150 net, 181.50 gross
        for label, partner, document_code, unit_price, discount, vat in (
            (
                "letter A reports the net unit price and the VAT apart",
                self.partner_ri,
                "1",
                100.0,
                "50.000000",
                "31.50",
            ),
            ("letter B reports the unit price with the VAT inside", self.partner_cf, "6", 121.0, "60.500000", None),
        ):
            with self.subTest(label), self.cr.savepoint() as savepoint:
                invoice = self._invoice_with_discounted_line(partner)
                self.assertEqual(invoice.l10n_latam_document_type_id.code, document_code)

                request_data = self._wsmtxca_request(invoice)

                # The section and the note do not reach ARCA, only the real line does
                self.assertEqual(len(request_data["arrayItems"]), 1)
                item = request_data["arrayItems"][0]
                # The amount is the behaviour; how many decimals it is written with
                # follows the Product Price precision and the battery checks it
                self.assertEqual(float(item["precioUnitario"]), unit_price)
                self.assertEqual(item["importeBonificacion"], discount)
                self.assertEqual(item["importeIVA"], vat)
                # importeItem is the same under both letters: it is what the customer pays
                self.assertEqual(item["importeItem"], "181.50")
                self.assertEqual(item["cantidad"], 2.0)
                savepoint.close()  # every case starts from the same situation

    def test_wsmtxca_items_negative_line_travels_without_quantity(self):
        """Task 68095: wsmtxca rejects a negative cantidad or precioUnitario for
        any unit of measure, "00" included, so a negative line goes out as
        bonificacion (99) carrying only its negative importeItem.

        Covers behaviour 19 of the survey, for lines that carry a product --
        which is every line that reaches here: a line with no product is now
        rejected outright (see test_wsmtxca_items_reject_line_without_product),
        so the "00" unit of measure and the catch-all behind it are unreachable
        by design.
        """
        invoice = self._create_invoice_ar(
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=500.0),
                self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=-100.0),
            ],
        )

        request_data = self._wsmtxca_request(invoice)

        items = request_data["arrayItems"]
        self.assertEqual(len(items), 2)
        positive, negative = items
        # The ordinary line keeps its unit of measure and reports quantity and price
        self.assertEqual(positive["codigoUnidadMedida"], 7)
        self.assertEqual(positive["cantidad"], 1.0)
        # The negative one is reported as a discount, with both offending fields omitted
        self.assertEqual(negative["codigoUnidadMedida"], 99)
        self.assertIsNone(negative["cantidad"])
        self.assertIsNone(negative["precioUnitario"])
        self.assertEqual(negative["importeItem"], "-121.00")

    def test_wsmtxca_items_reject_uom_without_afip_code(self):
        """Task 68095: a product whose unit of measure has no ARCA code is
        blocked instead of travelling with a made up one.

        Covers behaviour 17 of the survey.
        """
        # Take the ARCA code off the unit of measure the scenario product uses
        self.product_iva_21.uom_id.l10n_ar_afip_code = False
        invoice = self._create_invoice_ar()

        with self.assertRaisesRegex(UserError, "No AFIP code in .* UOM"):
            self._wsmtxca_request(invoice)

    def test_wsmtxca_line_details_delegate_for_other_journals(self):
        """Task 68095: only a wsmtxca journal gets the wsmtxca item format --
        every other journal, including one with no webservice at all, gets
        l10n_ar_edi's own.

        Covers behaviour 45 of the survey.
        """
        preprinted_journal = self._create_journal("preprinted", data={"code": "PREP1"})
        self.assertFalse(preprinted_journal.l10n_ar_afip_ws, "the scenario needs a journal with no webservice")
        invoice = self._create_invoice_ar(journal_id=preprinted_journal)
        base_lines, _tax_lines = invoice._get_rounded_base_and_tax_lines()

        details = invoice._get_line_details(base_lines=base_lines)

        # Upstream's shape, not this module's
        self.assertTrue(details)
        self.assertIn("Pro_ds", details[0])
        self.assertNotIn("codigoMtx", details[0])

    def test_wsmtxca_items_reject_line_without_product(self):
        """Task 68095: RG2904 reports product codes, so a line with no product
        is blocked before reaching ARCA, and every offending line is listed at
        once instead of one per attempt.

        Covers behaviour 44 of the survey.
        """
        invoice = self._create_invoice_ar(
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=1000.0),
                self._prepare_invoice_line(price_unit=100.0, tax_ids=self.tax_21, name="Servicio sin producto"),
                self._prepare_invoice_line(price_unit=50.0, tax_ids=self.tax_21, name="Otro sin producto"),
            ],
        )

        with self.assertRaisesRegex(UserError, "requires a product on every invoice line") as caught:
            self._wsmtxca_request(invoice)

        # Both offending lines are named, so they get fixed in one pass
        self.assertIn("Servicio sin producto", str(caught.exception))
        self.assertIn("Otro sin producto", str(caught.exception))
