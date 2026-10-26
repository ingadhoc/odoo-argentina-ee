from unittest.mock import patch

from odoo.addons.l10n_ar_edi.tests.common import TestArEdiCommon
from odoo.tests import tagged


@tagged("post_install", "post_install_l10n", "-at_install")
class TestWsfexLineDetails(TestArEdiCommon):
    @classmethod
    @TestArEdiCommon.setup_afip_ws("wsfex")
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.res_partner_barcelona_food
        cls.journal = cls._create_journal("wsfex")

    def _get_items(self, invoice):
        base_lines, _tax_lines = invoice._get_rounded_base_and_tax_lines()
        return invoice._get_line_details(base_lines=base_lines)

    def test_negative_line_sends_umed_99(self):
        invoice = self._create_invoice_ar(
            journal_id=self.journal,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=100),
                self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=-10),
            ],
        )
        product_item, discount_item = self._get_items(invoice)
        self.assertEqual(product_item["Pro_umed"], "07")
        self.assertEqual(discount_item["Pro_qty"], "0.00")
        self.assertEqual(discount_item["Pro_umed"], "99")

    def test_down_payment_line_sends_umed_97(self):
        invoice = self._create_invoice_ar(
            journal_id=self.journal,
            invoice_line_ids=[self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=100)],
        )
        line_class = type(self.env["account.move.line"])
        with patch.object(line_class, "_get_downpayment_lines", lambda line: line):
            (item,) = self._get_items(invoice)
        self.assertEqual(item["Pro_qty"], "0.00")
        self.assertEqual(item["Pro_umed"], "97")
