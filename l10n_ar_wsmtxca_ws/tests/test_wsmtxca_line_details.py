from odoo import Command
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestWsmtxcaLineDetails(TestArCommon):
    """Los items que se envian a WSMTXCA tienen que respetar la formula de ARCA
    (codigos 110/401/519) tanto con impuestos IVA incluido como no incluido."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls._create_journal("wsmtxcaws", data={"l10n_ar_afip_pos_system": "WSMTXCAWS"})
        cls.tax_21_included = cls.tax_21.copy({"name": "IVA 21% incluido", "price_include_override": "tax_included"})
        cls.product_iva_21.barcode = "4008789718044"

    def _create_wsmtxca_invoice(self, partner, tax, price_unit, quantity=1.0, discount=0.0):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "invoice_date": "2026-01-01",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_iva_21.id,
                            "price_unit": price_unit,
                            "quantity": quantity,
                            "discount": discount,
                            "tax_ids": [Command.set(tax.ids)],
                        }
                    )
                ],
            }
        )
        self.assertEqual(invoice.journal_id.l10n_ar_afip_ws, "wsmtxca")
        return invoice

    def _get_item(self, invoice):
        base_lines, _tax_lines = invoice._get_rounded_base_and_tax_lines()
        items = invoice._get_line_details(base_lines=base_lines)
        self.assertEqual(len(items), 1)
        return items[0]

    def _assert_item(self, item, precio_unitario, importe_item, importe_iva=None, bonificacion=None):
        self.assertAlmostEqual(float(item["precioUnitario"]), precio_unitario, places=2)
        self.assertAlmostEqual(float(item["importeItem"]), importe_item, places=2)
        if importe_iva is None:
            self.assertIsNone(item["importeIVA"])
        else:
            self.assertAlmostEqual(float(item["importeIVA"]), importe_iva, places=2)
        if bonificacion is None:
            self.assertIsNone(item["importeBonificacion"])
        else:
            self.assertAlmostEqual(float(item["importeBonificacion"]), bonificacion, places=2)

    def _assert_arca_taxable_amount(self, invoice, item):
        """Letra B: ARCA calcula el gravado como importeItem menos el IVA contenido en el item."""
        importe_item = float(item["importeItem"])
        self.assertAlmostEqual(importe_item - importe_item * 0.21 / 1.21, invoice.amount_untaxed, delta=0.01)
        self.assertAlmostEqual(importe_item, invoice.amount_total, delta=0.01)

    def test_invoice_b_tax_excluded(self):
        invoice = self._create_wsmtxca_invoice(self.partner_cf, self.tax_21, 100.0, quantity=2)
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "6")
        item = self._get_item(invoice)
        self._assert_item(item, precio_unitario=121.0, importe_item=242.0)
        self._assert_arca_taxable_amount(invoice, item)

    def test_invoice_b_tax_included(self):
        invoice = self._create_wsmtxca_invoice(self.partner_cf, self.tax_21_included, 23792.0)
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "6")
        item = self._get_item(invoice)
        self._assert_item(item, precio_unitario=23792.0, importe_item=23792.0)
        self._assert_arca_taxable_amount(invoice, item)

    def test_invoice_b_tax_included_discount(self):
        invoice = self._create_wsmtxca_invoice(self.partner_cf, self.tax_21_included, 121.0, discount=10)
        item = self._get_item(invoice)
        self._assert_item(item, precio_unitario=121.0, importe_item=108.9, bonificacion=12.1)
        self._assert_arca_taxable_amount(invoice, item)

    def test_invoice_a_tax_excluded(self):
        invoice = self._create_wsmtxca_invoice(self.res_partner_adhoc, self.tax_21, 100.0, quantity=2)
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "1")
        item = self._get_item(invoice)
        self._assert_item(item, precio_unitario=100.0, importe_item=242.0, importe_iva=42.0)

    def test_invoice_a_tax_included(self):
        invoice = self._create_wsmtxca_invoice(self.res_partner_adhoc, self.tax_21_included, 121.0, quantity=2)
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "1")
        item = self._get_item(invoice)
        self._assert_item(item, precio_unitario=100.0, importe_item=242.0, importe_iva=42.0)

    def test_invoice_a_tax_included_discount(self):
        invoice = self._create_wsmtxca_invoice(self.res_partner_adhoc, self.tax_21_included, 121.0, discount=10)
        item = self._get_item(invoice)
        self._assert_item(item, precio_unitario=100.0, importe_item=108.9, importe_iva=18.9, bonificacion=10.0)
