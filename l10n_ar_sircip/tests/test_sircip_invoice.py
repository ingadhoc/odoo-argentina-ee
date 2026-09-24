##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command
from odoo.tests import tagged

from .common import TestSircipCommon


@tagged("post_install", "-at_install")
class TestSircipInvoice(TestSircipCommon):
    def test_perceptions_by_campo7_digit(self):
        """Qué percepción SIRCIP lleva la factura según el padrón y la provincia de entrega.

        Fuente: planilla oficial "Aplicación Códigos" y Q&A CESSI de la Comisión Arbitral.
        - En el padrón: siempre "Percepción SIRCIP" con la alícuota de la letra, cualquiera sea el dígito
          del campo 7 (3 = adherida sin alta y sin sobretasa; 4 y 5 = no adherida, la provincial va por su
          propia línea de posición fiscal).
        - Dígito 2: además, "por falta de alta en (provincia)" en una línea aparte.
        - Letra A (0%): nada en la factura; con dígito 2, solo la sobretasa.
        - Fuera del padrón: 2% "por no inscripto" solo si la entrega es en una provincia adherida.
        """
        cases = [
            ("dígito 1: solo Percepción SIRCIP", "digit1", ["Percepción SIRCIP 3.00%"]),
            (
                "dígito 2: Percepción SIRCIP y falta de alta en Chaco, en líneas separadas",
                "digit2",
                ["Percepción SIRCIP 0.30%", "Percepción SIRCIP por falta de alta en Chaco"],
            ),
            ("dígito 3: Percepción SIRCIP, sin sobretasa", "digit3", ["Percepción SIRCIP 0.30%"]),
            ("dígito 4: Percepción SIRCIP, sin la provincial", "digit4", ["Percepción SIRCIP 0.30%"]),
            ("dígito 5: Percepción SIRCIP", "digit5", ["Percepción SIRCIP 0.30%"]),
            ("letra A: nada en la factura", "letter_a", []),
            (
                "letra A con dígito 2: solo la sobretasa",
                "letter_a_digit2",
                ["Percepción SIRCIP por falta de alta en Chaco"],
            ),
            (
                "fuera del padrón, entrega adherida: 2% por no inscripto",
                "not_registered",
                ["Percepción SIRCIP por no inscripto"],
            ),
            ("fuera del padrón, entrega no adherida: nada", "not_registered_not_adhered", []),
        ]
        for label, key, expected in cases:
            with self.subTest(label):
                invoice = self._sircip_invoice(self.partners[key])
                self.assertEqual(self._sircip_tax_names(invoice), expected)
                for line in invoice.line_ids.filtered("tax_line_id.l10n_ar_sircip_record_type"):
                    self.assertAlmostEqual(abs(line.balance), 1000.0 * line.tax_line_id.amount / 100.0, places=2)
                self.assert_sircip_invariants(invoice)

    def test_same_month_and_delivery_changes(self):
        """El padrón se consulta una vez por mes, pero la percepción se calcula en cada factura con la
        provincia de entrega de esa factura (el campo 7 se lee solo para la jurisdicción de entrega)."""
        partner = self.partners["digit2"]
        both = ["Percepción SIRCIP 0.30%", "Percepción SIRCIP por falta de alta en Chaco"]
        with self.subTest("la primera factura del mes lleva SIRCIP y sobretasa"):
            first = self._sircip_invoice(partner, post=True)
            self.assertEqual(self._sircip_tax_names(first), both)
            self.assert_sircip_invariants(first)
        with self.subTest("la segunda factura del mes mantiene la sobretasa"):
            second = self._sircip_invoice(partner)
            self.assertEqual(self._sircip_tax_names(second), both)
            self.assert_sircip_invariants(second)
        with self.subTest("con entrega en Salta se lee el dígito de Salta: sin sobretasa"):
            salta = self._delivery(partner, self.salta)
            third = self._sircip_invoice(partner, shipping=salta)
            self.assertEqual(self._sircip_tax_names(third), ["Percepción SIRCIP 0.30%"])
            self.assert_sircip_invariants(third)
        with self.subTest("cambiar la entrega de la factura recalcula las percepciones"):
            third.partner_shipping_id = partner
            self.assertEqual(self._sircip_tax_names(third), both)
            self.assert_sircip_invariants(third)
        with self.subTest("un solo registro del padrón por mes en el contacto, con CRC, letra y campo 7"):
            cache = partner.l10n_ar_partner_perception_ids.filtered("tax_id.l10n_ar_sircip_record_type")
            self.assertEqual(len(cache), 1)
            self.assertIn("crc:%s" % self.crc["digit2"], cache.ref)
            self.assertIn("letra:F", cache.ref)

    def test_sale_order_delivery(self):
        """En el pedido de venta la percepción SIRCIP también sale de la dirección de entrega del pedido, y la factura
        que se genera la conserva (l10n_ar_sale pasa la entrega con l10n_ar_delivery_partner_id)."""
        if self.env["ir.module.module"]._get("l10n_ar_sale").state != "installed":
            self.skipTest("l10n_ar_sale no está instalado: las percepciones del pedido las calcula ese módulo")
        partner = self.partners["digit2"]
        salta = self._delivery(partner, self.salta)
        # Facturar lo pedido: el default depende de los módulos instalados (con stock es lo entregado)
        self.product_iva_21.invoice_policy = "order"
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
        with self.subTest("entrega en Salta: se lee el dígito de Salta, sin sobretasa"):
            self.assertEqual(sircip_names(order.order_line.tax_id), ["Percepción SIRCIP 0.30%"])
        with self.subTest("cambiar la entrega a Chaco recalcula las percepciones del pedido"):
            order.partner_shipping_id = partner
            order._l10n_ar_recompute_fiscal_position_taxes()
            self.assertEqual(sircip_names(order.order_line.tax_id), both)
        with self.subTest("la factura del pedido conserva la entrega y las percepciones"):
            order.action_confirm()
            invoice = order._create_invoices()
            self.assertEqual(invoice.partner_shipping_id, partner)
            self.assertEqual(self._sircip_tax_names(invoice), both)
            self.assert_sircip_invariants(invoice)
