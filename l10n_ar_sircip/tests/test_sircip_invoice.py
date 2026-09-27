##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command
from odoo.exceptions import RedirectWarning
from odoo.tests import Form, tagged

from .common import TestSircipCommon


@tagged("post_install", "-at_install")
class TestSircipInvoice(TestSircipCommon):
    def test_perceptions_by_campo7_digit(self):
        """SIRCIP perceptions of an invoice by padron data and delivery province.

        In the padron, "Percepción SIRCIP" at the letter aliquot for any digit, plus the surcharge on digit 2;
        letter A adds only the surcharge. Not in the padron, 2% "no inscripto" only for adhered deliveries.
        """
        cases = [
            ("digit 1: only Percepción SIRCIP", "digit1", ["Percepción SIRCIP 3.00%"]),
            (
                "digit 2: Percepción SIRCIP and falta de alta en Chaco, on separate lines",
                "digit2",
                ["Percepción SIRCIP 0.30%", "Percepción SIRCIP por falta de alta en Chaco"],
            ),
            ("digit 3: Percepción SIRCIP, no surcharge", "digit3", ["Percepción SIRCIP 0.30%"]),
            ("digit 4: Percepción SIRCIP, without the provincial one", "digit4", ["Percepción SIRCIP 0.30%"]),
            ("digit 5: Percepción SIRCIP", "digit5", ["Percepción SIRCIP 0.30%"]),
            ("letter A: nothing on the invoice", "letter_a", []),
            (
                "letter A with digit 2: only the surcharge",
                "letter_a_digit2",
                ["Percepción SIRCIP por falta de alta en Chaco"],
            ),
            (
                "not in padron, adhered delivery: 2% no inscripto",
                "not_registered",
                ["Percepción SIRCIP por no inscripto"],
            ),
            ("not in padron, non-adhered delivery: nothing", "not_registered_not_adhered", []),
        ]
        for label, key, expected in cases:
            with self.subTest(label):
                invoice = self._sircip_invoice(self.partners[key])
                self.assertEqual(self._sircip_tax_names(invoice), expected)
                for line in invoice.line_ids.filtered("tax_line_id.l10n_ar_sircip_record_type"):
                    self.assertAlmostEqual(abs(line.balance), 1000.0 * line.tax_line_id.amount / 100.0, places=2)
                self.assert_sircip_invariants(invoice)

    def test_same_month_and_delivery_changes(self):
        """The padron is read once a month, but each invoice computes its perceptions with its own delivery
        province."""
        partner = self.partners["digit2"]
        both = ["Percepción SIRCIP 0.30%", "Percepción SIRCIP por falta de alta en Chaco"]
        with self.subTest("the first invoice of the month has SIRCIP and the surcharge of the delivery province"):
            first = self._sircip_invoice(partner, post=True)
            self.assertEqual(self._sircip_tax_names(first), both)
            surcharge = first.invoice_line_ids.tax_ids.filtered(lambda x: "falta de alta" in x.name)
            self.assertEqual(surcharge.l10n_ar_state_id, self.chaco)
            self.assert_sircip_invariants(first)
        with self.subTest("the second invoice of the month uses the stored record, even without the padron file"):
            self.env["res.company.jurisdiction.padron"].search([("state_id", "=", self.sircip_state.id)]).unlink()
            second = self._sircip_invoice(partner)
            self.assertEqual(self._sircip_tax_names(second), both)
            self.assert_sircip_invariants(second)
        with self.subTest("delivery in Salta reads the Salta digit: no surcharge"):
            salta = self._delivery(partner, self.salta)
            third = self._sircip_invoice(partner, shipping=salta)
            self.assertEqual(self._sircip_tax_names(third), ["Percepción SIRCIP 0.30%"])
            self.assert_sircip_invariants(third)
        with self.subTest("changing the invoice delivery recomputes the perceptions"):
            third.partner_shipping_id = partner
            self.assertEqual(self._sircip_tax_names(third), both)
            self.assert_sircip_invariants(third)
        with self.subTest("a single padron record per month on the contact, with CRC, letter and field 7"):
            cache = partner.l10n_ar_partner_perception_ids.filtered("tax_id.l10n_ar_sircip_record_type")
            self.assertEqual(len(cache), 1)
            self.assertIn("crc:%s" % self.crc["digit2"], cache.ref)
            self.assertIn("letra:F", cache.ref)
            self.assertFalse(salta.l10n_ar_partner_perception_ids, "delivery addresses store no padron record")

    def test_digit4_needs_the_provincial_perception(self):
        """Digit 4 in the delivery province: that province perceives too, through its own fiscal position. Without
        it the invoice and the sale order are stopped, pointing to the fiscal position to create or fix."""
        partner = self.partners["digit4"]
        with self.subTest("no fiscal position perceives Corrientes: it offers a new one, ready to adjust"):
            invoice = self._sircip_invoice(partner)
            with self.assertRaises(RedirectWarning) as error:
                invoice.action_post()
            message, action = error.exception.args[:2]
            self.assertIn("Corrientes", message)
            self.assertNotIn("res_id", action)
            defaults = action["context"]
            self.assertEqual(defaults["default_state_ids"], [Command.set(self.corrientes.ids)])
            new_fp = Form(self.env["account.fiscal.position"].with_context(**defaults)).save()
            self.assertEqual(new_fp.state_ids, self.corrientes, "the country onchange keeps the preset province")
            self.assertEqual(
                sorted(new_fp.l10n_ar_tax_ids.default_tax_id.mapped("l10n_ar_state_id.name")),
                ["Corrientes", "SIRCIP"],
            )
            new_fp.unlink()
        corrientes_fp = self._corrientes_fiscal_position(partner, auto_apply=False)
        with self.subTest("one exists but was not applied: it points to it and says why"):
            invoice = self._sircip_invoice(partner)
            with self.assertRaises(RedirectWarning) as error:
                invoice.action_post()
            message, action = error.exception.args[:2]
            self.assertEqual(action["res_id"], corrientes_fp.id)
            self.assertIn("not detected automatically", message)
        with self.subTest("with its fiscal position the invoice has both perceptions"):
            self.assertTrue(corrientes_fp.l10n_ar_tax_ids.filtered(lambda x: x._l10n_ar_is_sircip()))
            invoice = self._sircip_invoice(partner, post=True, fiscal_position=corrientes_fp)
            self.assertEqual(
                sorted(invoice.invoice_line_ids.tax_ids.filtered("l10n_ar_state_id").mapped("name")),
                ["P. IIBB CTS 3%", "Percepción SIRCIP 0.30%"],
            )
        with self.subTest("the sale order is stopped when confirmed"):
            if self.env["ir.module.module"]._get("l10n_ar_sale").state != "installed":
                self.skipTest("l10n_ar_sale is not installed: it checks the order perceptions")
            order = self.env["sale.order"].create(
                {
                    "partner_id": partner.id,
                    "fiscal_position_id": self.fiscal_position.id,
                    "company_id": self.company_ri.id,
                    "order_line": [Command.create({"product_id": self.product_iva_21.id, "price_unit": 1000.0})],
                }
            )
            with self.assertRaises(RedirectWarning):
                order.action_confirm()

    def test_sale_order_delivery(self):
        """On the sale order, the SIRCIP perception also follows the order delivery address (passed by
        l10n_ar_sale)."""
        if self.env["ir.module.module"]._get("l10n_ar_sale").state != "installed":
            self.skipTest("l10n_ar_sale is not installed: it computes the order perceptions")
        partner = self.partners["digit2"]
        salta = self._delivery(partner, self.salta)
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "partner_shipping_id": salta.id,
                "fiscal_position_id": self.fiscal_position.id,
                "company_id": self.company_ri.id,
                "order_line": [Command.create({"product_id": self.product_iva_21.id, "price_unit": 1000.0})],
            }
        )
        sircip_names = lambda taxes: sorted(taxes.filtered("l10n_ar_sircip_record_type").mapped("name"))  # noqa: E731
        both = ["Percepción SIRCIP 0.30%", "Percepción SIRCIP por falta de alta en Chaco"]
        with self.subTest("delivery in Salta: reads the Salta digit, no surcharge"):
            self.assertEqual(sircip_names(order.order_line.tax_id), ["Percepción SIRCIP 0.30%"])
        with self.subTest("changing the delivery to Chaco recomputes the order perceptions"):
            order.partner_shipping_id = partner
            order._l10n_ar_recompute_fiscal_position_taxes()
            self.assertEqual(sircip_names(order.order_line.tax_id), both)
