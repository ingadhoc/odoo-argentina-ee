from odoo.tests import tagged

from .common import TestWsmtxcaCommon


@tagged("post_install", "post_install_l10n", "-at_install", *TestWsmtxcaCommon.extra_tags)
class TestWsmtxcaCaeRequest(TestWsmtxcaCommon):
    """The envelope around the items: dates, totals, VAT subtotals, tributes and
    the keys that only some document types carry."""

    def test_wsmtxca_cae_request_envelope(self):
        """Task 68095: the request identifies the document the way wsmtxca wants
        -- ISO dates instead of the compact ones the other webservices use, one
        VAT subtotal per rate in play, and the perceptions as other tributes.

        Covers behaviours 21, 23 and 24 of the survey.
        """
        # The scenario turns the IIBB perception on and gives it a rate: the base
        # ships it disabled and at 0%, which would make it invisible in the request
        perception = self._search_tax("percepcion_iibb_ba")
        perception.write({"active": True, "amount": 3.5})

        invoice = self._create_invoice_ar(
            invoice_line_ids=[
                # 21% and 10,5% together, and the 10,5% one also bears the perception
                self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=1000.0),
                self._prepare_invoice_line(product_id=self.product_iva_105, price_unit=2000.0),
            ],
        )
        invoice.invoice_line_ids.filtered(lambda line: line.product_id == self.product_iva_105).tax_ids = [
            (4, perception.id)
        ]
        self.assertIn(perception.name, invoice.invoice_line_ids.tax_ids.mapped("name"))

        request_data = self._wsmtxca_request(invoice)

        with self.subTest("dates travel in ISO format, not in the compact one the other webservices use"):
            self.assertEqual(request_data["fechaEmision"], invoice.invoice_date.strftime("%Y-%m-%d"))

        with self.subTest("the document is identified by type, point of sale and number"):
            self.assertEqual(request_data["codigoTipoComprobante"], int(invoice.l10n_latam_document_type_id.code))
            self.assertEqual(request_data["numeroPuntoVenta"], int(self.journal.l10n_ar_afip_pos_number))
            self.assertEqual(request_data["numeroComprobante"], 12345678)

        with self.subTest("every VAT rate in play gets its own subtotal, keyed by the ARCA code"):
            # 5 is 21% and 4 is 10,5%
            self.assertEqual(sorted(entry["codigo"] for entry in request_data["arraySubtotalesIVA"]), ["4", "5"])

        with self.subTest("the perception travels as another tribute, with the wsmtxca key names"):
            tributes = request_data["arrayOtrosTributos"]
            self.assertEqual(len(tributes), 1)
            self.assertEqual(sorted(tributes[0]), ["baseImponible", "codigo", "descripcion", "importe"])
            self.assertEqual(request_data["importeOtrosTributos"], tributes[0]["importe"])

    def test_wsmtxca_cae_request_foreign_currency(self):
        """Task 68095: in foreign currency the request carries the rate ARCA
        expects and declares whether the invoice is settled in that currency.

        Covers behaviours 26 and 29 of the survey.
        """
        self._prepare_multicurrency_values()
        usd = self.env.ref("base.USD")

        with self.subTest("in pesos the settlement key is not reported at all"):
            request_data = self._wsmtxca_request(self._create_invoice_ar())
            self.assertEqual(request_data["codigoMoneda"], "PES")
            self.assertNotIn("cancelaEnMismaMonedaExtranjera", request_data)

        with self.subTest("in dollars the rate and the settlement key are reported"):
            invoice = self._create_invoice_ar(currency_id=usd)
            request_data = self._wsmtxca_request(invoice, document_number="12345-12345679")
            self.assertEqual(request_data["codigoMoneda"], "DOL")
            # The rate travels inverted: pesos per unit of foreign currency
            self.assertEqual(request_data["cotizacionMoneda"], "%.6f" % (1 / invoice.invoice_currency_rate))
            self.assertEqual(request_data["cancelaEnMismaMonedaExtranjera"], "N")

    def test_wsmtxca_cae_request_mipyme_due_date(self):
        """Task 68095: a MiPyME invoice always reports the payment due date --
        ARCA rejects it otherwise (WSMT148).

        Covers behaviour 27 of the survey.
        """
        mipyme = self.env["l10n_latam.document.type"].search(
            [("code", "=", "201"), ("country_id", "=", self.env.ref("base.ar").id)], limit=1
        )
        invoice = self._create_invoice_ar(l10n_latam_document_type_id=mipyme)
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "201")

        request_data = self._wsmtxca_request(invoice)

        self.assertTrue(request_data["fechaVencimientoPago"])
        self.assertEqual(request_data["fechaVencimientoPago"], invoice.invoice_date_due.strftime("%Y-%m-%d"))

    def test_wsmtxca_credit_note_reports_the_related_invoice(self):
        """Task 68095: a credit note carries the invoice it cancels, keyed the
        wsmtxca way, so ARCA can match them.

        Covers behaviour 25 of the survey.
        """
        invoice = self._create_invoice_ar()
        self._wsmtxca_request(invoice)

        # Reversing produces the credit note that has to point back at the invoice
        credit_note = self._reverse_invoice(invoice, reason="Mercadería defectuosa")
        request_data = self._wsmtxca_request(credit_note, document_number="12345-12345679")

        related = request_data["arrayComprobantesAsociados"]
        self.assertEqual(len(related), 1)
        self.assertEqual(
            related[0],
            {
                "codigoTipoComprobante": invoice.l10n_latam_document_type_id.code,
                "numeroPuntoVenta": invoice.journal_id.l10n_ar_afip_pos_number,
                "numeroComprobante": 12345678,
            },
        )

    def test_wsmtxca_reduced_vat_rates_reach_the_subtotals(self):
        """Task 68095: the 5% and 2,5% rates report their own VAT subtotal.

        Until vat_needed grew, only 10,5%, 21% and 27% were reported, while
        _l10n_ar_get_amounts counted the base of any code other than 0, 1 and 2
        into importeGravado and the tax into importeTotal -- so an invoice at 5%
        left ARCA's envelope short by exactly that VAT. The battery's
        assert_arca_total_identity is what closes it on every case.
        """
        for label, tax_type, code, amount in (
            ("5% reports subtotal code 8", "iva_5", "8", "50.00"),
            ("2,5% reports subtotal code 9", "iva_025", "9", "25.00"),
        ):
            with self.subTest(label), self.cr.savepoint() as savepoint:
                tax = self._search_tax(tax_type)
                invoice = self._create_invoice_ar(
                    invoice_line_ids=[
                        self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=1000.0, tax_ids=tax)
                    ],
                )

                request_data = self._wsmtxca_request(invoice)

                self.assertEqual(request_data["arraySubtotalesIVA"], [{"codigo": code, "importe": amount}])
                savepoint.close()  # every case starts from the same situation

    def test_wsmtxca_invoice_without_related_reports_no_association(self):
        """Task 68095: an ordinary invoice carries no association array -- ARCA
        rejects an empty one.

        Covers behaviour 25 of the survey, negative side.
        """
        request_data = self._wsmtxca_request(self._create_invoice_ar())
        self.assertIsNone(request_data["arrayComprobantesAsociados"])
