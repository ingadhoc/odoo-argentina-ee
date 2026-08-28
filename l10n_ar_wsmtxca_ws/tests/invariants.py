"""Battery of invariants for every wsmtxca CAE request.

These are the properties that must hold after *any* wsmtxca request is built,
whatever the individual test went looking for. ``TestWsmtxcaCommon`` runs the
whole battery on every request it builds, so each suite gets them for free.

The battery has no switches to skip an invariant. A scenario that legitimately
breaks one declares the exception in the test itself, in plain sight and with
the reason next to it.

It lives in this module (and not in a module further up the chain) because
every invariant reads keys of the wsmtxca payload, which is defined here:
``l10n_ar_edi`` is Odoo's and knows nothing about wsmtxca, and
``saas_client_l10n_ar`` does not build ARCA requests.
"""

from odoo.tools.float_utils import float_compare


def payload_float(value):
    """Read a payload amount as a float.

    wsmtxca_get_cae_request mixes types on purpose: most amounts travel as
    strings built with float_repr, a few as plain floats, and the optional ones
    as None.
    """
    if value is None:
        return 0.0
    return float(value)


def payload_decimals(value):
    """Count the decimal digits actually written in the payload."""
    text = value if isinstance(value, str) else repr(float(value))
    return len(text.partition(".")[2])


class WsmtxcaInvariants:
    """Mixin with the battery. Inherited by TestWsmtxcaCommon."""

    #: decimals ARCA accepts for each payload amount, per the wsmtxca spec
    WSMTXCA_ITEM_MAX_DECIMALS = {"importeItem": 2, "importeIVA": 2, "importeBonificacion": 6}
    WSMTXCA_RATE_MAX_DECIMALS = 6

    def assert_wsmtxca_invariants(self, invoice, request_data):
        """Run the whole battery over one built request."""
        self.assert_amounts_add_up(request_data)
        self.assert_arca_total_identity(request_data)
        self.assert_items_add_up_to_total(request_data)
        self.assert_no_negative_quantities(request_data)
        self.assert_items_have_codigo_mtx(request_data)
        self.assert_declared_precision(request_data)
        self.assert_move_is_sound(invoice)

    def assert_amounts_add_up(self, request_data):
        """ARCA cross-check: the subtotal is the sum of the three taxable bases."""
        expected = request_data["importeGravado"] + request_data["importeExento"] + request_data["importeNoGravado"]
        self.assertEqual(
            float_compare(request_data["importeSubtotal"], expected, precision_digits=2),
            0,
            "importeSubtotal (%s) must equal importeGravado + importeExento + importeNoGravado (%s)"
            % (request_data["importeSubtotal"], expected),
        )

    def assert_arca_total_identity(self, request_data):
        """The identity ARCA cross-checks on the envelope: the total is the
        subtotal plus every VAT subtotal plus the non-VAT tributes.

        This is what caught the 5% and 2,5% rates missing from
        arraySubtotalesIVA: _l10n_ar_get_amounts counts the base of *any* code
        other than 0, 1 and 2 into importeGravado and the tax into importeTotal,
        so a rate left out of wsmtxca_get_cae_request's vat_needed broke the
        identity by exactly its VAT. Code 3 (0%) stays out of vat_needed on
        purpose: its amount is zero, so it does not move this identity.
        """
        vat_total = sum(payload_float(entry["importe"]) for entry in request_data["arraySubtotalesIVA"] or [])
        expected = request_data["importeSubtotal"] + vat_total + payload_float(request_data.get("importeOtrosTributos"))
        self.assertEqual(
            float_compare(request_data["importeTotal"], expected, precision_digits=2),
            0,
            "importeTotal (%s) must equal importeSubtotal plus the VAT subtotals plus importeOtrosTributos (%s)"
            % (request_data["importeTotal"], expected),
        )

    def assert_items_add_up_to_total(self, request_data):
        """ARCA cross-check behind error 519: the items plus the non-VAT
        tributes must add up to the invoice total."""
        items_total = sum(payload_float(item["importeItem"]) for item in request_data["arrayItems"])
        expected = items_total + payload_float(request_data.get("importeOtrosTributos"))
        self.assertEqual(
            float_compare(request_data["importeTotal"], expected, precision_digits=2),
            0,
            "importeTotal (%s) must equal the sum of importeItem plus importeOtrosTributos (%s)"
            % (request_data["importeTotal"], expected),
        )

    def assert_no_negative_quantities(self, request_data):
        """wsmtxca rejects a negative cantidad or precioUnitario for *any* unit
        of measure, "00" included: such a line must travel as importeItem only."""
        for position, item in enumerate(request_data["arrayItems"], start=1):
            for key in ("cantidad", "precioUnitario"):
                if item[key] is None:
                    continue
                self.assertGreaterEqual(
                    payload_float(item[key]),
                    0.0,
                    "item %s reports a negative %s (%s); wsmtxca rejects it" % (position, key, item[key]),
                )

    def assert_items_have_codigo_mtx(self, request_data):
        """Every item carries the 13-digit product code the webservice is named after."""
        for position, item in enumerate(request_data["arrayItems"], start=1):
            codigo = item["codigoMtx"]
            self.assertTrue(
                isinstance(codigo, str) and codigo.isdigit() and len(codigo) == 13,
                "item %s has an invalid codigoMtx (%r); ARCA expects 13 digits" % (position, codigo),
            )

    def assert_declared_precision(self, request_data):
        """No amount travels with more decimals than ARCA declares for it."""
        for position, item in enumerate(request_data["arrayItems"], start=1):
            for key, max_decimals in self.WSMTXCA_ITEM_MAX_DECIMALS.items():
                if item.get(key) is None:
                    continue
                self.assertLessEqual(
                    payload_decimals(item[key]),
                    max_decimals,
                    "item %s reports %s with more than %s decimals (%s)" % (position, key, max_decimals, item[key]),
                )
        self.assertLessEqual(
            payload_decimals(request_data["cotizacionMoneda"]),
            self.WSMTXCA_RATE_MAX_DECIMALS,
            "cotizacionMoneda reports more than %s decimals (%s)"
            % (self.WSMTXCA_RATE_MAX_DECIMALS, request_data["cotizacionMoneda"]),
        )

    def assert_move_is_sound(self, invoice):
        """Building the request never leaves the accounting entry behind."""
        self.assertEqual(invoice.state, "posted", "the invoice the request was built from is not posted")
        balance = sum(invoice.line_ids.mapped("balance"))
        self.assertEqual(
            float_compare(balance, 0.0, precision_digits=2), 0, "the accounting entry does not balance (%s)" % balance
        )
        self.assertTrue(invoice.l10n_ar_afip_auth_code, "the posted invoice has no ARCA authorization code")
