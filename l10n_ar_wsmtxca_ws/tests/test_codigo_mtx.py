from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestWsmtxcaCommon


@tagged("post_install", "post_install_l10n", "-at_install", *TestWsmtxcaCommon.extra_tags)
class TestWsmtxcaCodigoMtx(TestWsmtxcaCommon):
    """The product coding is what RG2904 is about: every line has to travel with
    a code ARCA recognises, either the product's own GTIN or one of the generic
    ones."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A physical product with no GTIN loaded: the case the module must reject
        cls.product_without_barcode = cls.env["product.product"].create(
            {"name": "Cabinet with no GTIN", "type": "consu", "taxes_id": [(6, 0, cls.tax_21.ids)]}
        )
        # A GTIN that is not a GS1 code: the other case the module must reject
        cls.product_bad_barcode = cls.env["product.product"].create(
            {"name": "Cabinet with a bad GTIN", "type": "consu", "barcode": "NOT-A-GTIN"}
        )

    def _line(self, **line_args):
        """A single draft invoice line to hand to _get_codigoMtx."""
        invoice = self._create_invoice_ar(invoice_line_ids=[self._prepare_invoice_line(**line_args)])
        return invoice, invoice.invoice_line_ids

    def test_wsmtxca_codigo_mtx_per_kind_of_line(self):
        """Task 68095: each kind of line resolves to the codigoMtx ARCA expects.

        Covers behaviours 8 to 13 of the survey.
        """
        for label, line_args, expected in (
            ("a 13 digit GTIN travels as is", {"product_id": self.product_iva_21, "price_unit": 100}, "7791111111118"),
            (
                "an 8 digit GTIN is padded to 13",
                {"product_id": self.product_iva_105, "price_unit": 100},
                "0000077922228",
            ),
            (
                "a 12 digit GTIN is padded to 13",
                {"product_id": self.product_iva_105_perc, "price_unit": 100},
                "0779333333336",
            ),
            (
                "a service with no GTIN falls back to the generic services code",
                {"product_id": self.service_iva_27, "price_unit": 100},
                "7790001001078",
            ),
            (
                # Unreachable through the real flow: _get_line_details rejects a
                # line with no product. Kept because _get_codigoMtx still
                # documents the fallback and other callers could hit it.
                "a line with no product falls back to the generic sales code",
                {"price_unit": 100, "tax_ids": self.tax_21},
                "7790001001054",
            ),
            (
                "a negative line with no GTIN falls back to the generic discounts code",
                {"product_id": self.product_without_barcode, "price_unit": -100},
                "7790001001030",
            ),
        ):
            with self.subTest(label), self.cr.savepoint() as savepoint:
                invoice, line = self._line(**line_args)
                self.assertEqual(invoice._get_codigoMtx(line), expected)
                savepoint.close()  # every case starts from the same situation

    def test_wsmtxca_codigo_mtx_rejects_what_arca_would(self):
        """Task 68095: the two positive controls -- the module blocks the lines
        ARCA has no code for, instead of inventing one.

        Covers behaviours 9 and 13 of the survey.
        """
        with self.subTest("a GTIN that is not GS1 is rejected"), self.cr.savepoint() as savepoint:
            invoice, line = self._line(product_id=self.product_bad_barcode, price_unit=100)
            with self.assertRaisesRegex(UserError, "invalid barcode for ARCA"):
                invoice._get_codigoMtx(line)
            savepoint.close()

        with self.subTest("a physical product with no GTIN is rejected"):
            invoice, line = self._line(product_id=self.product_without_barcode, price_unit=100)
            with self.assertRaisesRegex(UserError, "does not have a valid Codigo MTX"):
                invoice._get_codigoMtx(line)
