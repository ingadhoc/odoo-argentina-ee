"""Each invariant of the battery, probed in both directions.

A shared battery concentrates risk: if one of its assertions stops looking,
every suite stays green while verifying nothing. So each invariant is exercised
twice -- with a sound request (it must not complain) and with the exact defect
it exists to catch (it must complain).
"""

import copy

from odoo.tests import tagged

from .common import TestWsmtxcaCommon

#: A request that satisfies every invariant. Each test deep-copies it and
#: breaks one thing.
SOUND_REQUEST = {
    "importeTotal": 121.0,
    "importeSubtotal": 100.0,
    "importeGravado": 100.0,
    "importeExento": 0.0,
    "importeNoGravado": 0.0,
    "importeOtrosTributos": None,
    "arraySubtotalesIVA": [{"codigo": "5", "importe": "21.00"}],
    "cotizacionMoneda": "1.000000",
    "arrayItems": [
        {
            "codigoMtx": "7791111111118",
            "descripcion": "Large Cabinet (VAT 21)",
            "cantidad": 1.0,
            "precioUnitario": "100.000",
            "importeItem": "121.00",
            "importeIVA": "21.00",
            "importeBonificacion": None,
        }
    ],
}


@tagged("post_install", "post_install_l10n", "-at_install", *TestWsmtxcaCommon.extra_tags)
class TestWsmtxcaInvariants(TestWsmtxcaCommon):
    def _broken(self, **overrides):
        """A copy of the sound request with the top-level keys replaced."""
        request = copy.deepcopy(SOUND_REQUEST)
        request.update(overrides)
        return request

    def _broken_item(self, **overrides):
        """A copy of the sound request with the single item's keys replaced."""
        request = copy.deepcopy(SOUND_REQUEST)
        request["arrayItems"][0].update(overrides)
        return request

    def test_invariant_amounts_add_up(self):
        """The subtotal cross-check catches a subtotal that is not the sum of the bases."""
        with self.subTest("a sound request does not complain"):
            self.assert_amounts_add_up(SOUND_REQUEST)
        with self.subTest("a subtotal that ignores a base is caught"):
            with self.assertRaises(AssertionError):
                self.assert_amounts_add_up(self._broken(importeNoGravado=50.0))

    def test_invariant_arca_total_identity(self):
        """The envelope cross-check catches VAT that the total counts and no
        subtotal reports -- the shape survey scenario 43 would take."""
        with self.subTest("a sound request does not complain"):
            self.assert_arca_total_identity(SOUND_REQUEST)
        with self.subTest("a VAT rate missing from the subtotals is caught"):
            # Exactly what dropping code 8 or 9 from vat_needed would produce
            with self.assertRaises(AssertionError):
                self.assert_arca_total_identity(self._broken(arraySubtotalesIVA=[]))
        with self.subTest("a tribute left out of the total is caught"):
            with self.assertRaises(AssertionError):
                self.assert_arca_total_identity(self._broken(importeOtrosTributos=10.0))

    def test_invariant_items_add_up_to_total(self):
        """The error-519 cross-check catches items that do not add up to the total."""
        with self.subTest("a sound request does not complain"):
            self.assert_items_add_up_to_total(SOUND_REQUEST)
        with self.subTest("an item reporting the net instead of the total is caught"):
            with self.assertRaises(AssertionError):
                self.assert_items_add_up_to_total(self._broken_item(importeItem="100.00"))
        with self.subTest("a tribute left out of the total is caught"):
            with self.assertRaises(AssertionError):
                self.assert_items_add_up_to_total(self._broken(importeOtrosTributos=10.0))

    def test_invariant_no_negative_quantities(self):
        """The check catches the negative cantidad/precioUnitario wsmtxca rejects."""
        with self.subTest("a sound request does not complain"):
            self.assert_no_negative_quantities(SOUND_REQUEST)
        with self.subTest("a negative quantity is caught"):
            with self.assertRaises(AssertionError):
                self.assert_no_negative_quantities(self._broken_item(cantidad=-1.0))
        with self.subTest("a negative unit price is caught"):
            with self.assertRaises(AssertionError):
                self.assert_no_negative_quantities(self._broken_item(precioUnitario="-100.000"))
        with self.subTest("omitting both fields is the accepted way out"):
            self.assert_no_negative_quantities(self._broken_item(cantidad=None, precioUnitario=None))

    def test_invariant_items_have_codigo_mtx(self):
        """The check catches a product code ARCA would not accept."""
        with self.subTest("a sound request does not complain"):
            self.assert_items_have_codigo_mtx(SOUND_REQUEST)
        with self.subTest("a code that is not 13 digits long is caught"):
            with self.assertRaises(AssertionError):
                self.assert_items_have_codigo_mtx(self._broken_item(codigoMtx="77911"))
        with self.subTest("a non numeric code is caught"):
            with self.assertRaises(AssertionError):
                self.assert_items_have_codigo_mtx(self._broken_item(codigoMtx="ABC1111111118"))
        with self.subTest("a missing code is caught"):
            with self.assertRaises(AssertionError):
                self.assert_items_have_codigo_mtx(self._broken_item(codigoMtx=None))

    def test_invariant_declared_precision(self):
        """The check catches an amount with more decimals than ARCA accepts."""
        with self.subTest("a sound request does not complain"):
            self.assert_declared_precision(SOUND_REQUEST)
        with self.subTest("an item amount with four decimals is caught"):
            with self.assertRaises(AssertionError):
                self.assert_declared_precision(self._broken_item(importeItem="121.0000"))
        with self.subTest("a rate with more than six decimals is caught"):
            with self.assertRaises(AssertionError):
                self.assert_declared_precision(self._broken(cotizacionMoneda="1.0000000"))
        with self.subTest("the six decimals of importeBonificacion are allowed"):
            self.assert_declared_precision(self._broken_item(importeBonificacion="10.123456"))

    def test_invariant_move_is_sound(self):
        """The check catches an entry that never got posted."""
        invoice = self._create_invoice_ar()
        with self.subTest("a draft invoice is caught"):
            with self.assertRaises(AssertionError):
                self.assert_move_is_sound(invoice)
        with self.subTest("the same invoice, posted, does not complain"):
            self._post(invoice)
            self.assert_move_is_sound(invoice)
