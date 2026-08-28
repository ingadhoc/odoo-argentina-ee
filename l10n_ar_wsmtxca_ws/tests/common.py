from odoo.addons.l10n_ar_edi.tests.common import ArMockedClient, TestArEdiCommon

from .invariants import WsmtxcaInvariants

#: GTIN codes handed to the scenario products. Real length variety on purpose:
#: _get_codigoMtx pads 8 and 12 digit codes to 13.
SCENARIO_BARCODES = {
    "product_iva_21": "7791111111118",
    "product_iva_105": "77922228",
    "product_iva_105_perc": "779333333336",
    "product_iva_exento": "7794444444445",
    "product_no_gravado": "7795555555552",
    "product_iva_cero": "7796666666669",
}


class TestWsmtxcaCommon(WsmtxcaInvariants, TestArEdiCommon):
    """Scenario configuration for the wsmtxca suites.

    Sits on top of l10n_ar_edi's common, which already provides the environment
    (ar_ri chart template, taxes, products) and the local-validation setup: with
    l10n_ar_afip_ws_environment='testing' and no certificate,
    _is_dummy_afip_validation() is True and posting an invoice never reaches ARCA.

    Two things upstream does not have and this class adds:

    * the WSMTXCA entry in the POS-system mapping, so _create_journal('wsmtxca')
      builds the journal;
    * a _validate_and_review that knows about wsmtxca -- the upstream one walks
      an if/elif over wsfe/wsfex/wsbfe and ends in self.fail().
    """

    @classmethod
    @TestArEdiCommon.setup_afip_ws("wsmtxca")
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.res_partner_adhoc
        cls.journal = cls._create_journal("wsmtxca")
        # wsmtxca refuses a physical product without a GS1/GTIN code, so the
        # scenario loads one on every product the suites invoice.
        for attribute, barcode in SCENARIO_BARCODES.items():
            getattr(cls, attribute).barcode = barcode

    @classmethod
    def _get_afip_pos_system_real_name(cls):
        mapping = super()._get_afip_pos_system_real_name()
        mapping.update({"WSMTXCA": "WSMTXCAWS"})
        return mapping

    def _wsmtxca_request(self, invoice, document_number="12345-12345678"):
        """Post the invoice and build the CAE request the way the module would.

        Returns the request payload, after running the whole invariants battery
        over it -- every suite gets layer 2 without asking for it.
        """
        self._post(invoice)
        invoice.l10n_latam_document_number = document_number
        request_data = invoice.wsmtxca_get_cae_request(ArMockedClient())
        self.assert_wsmtxca_invariants(invoice, request_data)
        return request_data

    def _validate_and_review(self, invoice, test_name: str, document_number="12345-12345678", skip_assert_json=False):
        """Extend to build the request through wsmtxca_get_cae_request.

        The upstream implementation only knows wsfe, wsfex and wsbfe and calls
        self.fail() for anything else.
        """
        if invoice.journal_id.l10n_ar_afip_ws != "wsmtxca":
            return super()._validate_and_review(invoice, test_name, document_number, skip_assert_json)
        return self._wsmtxca_request(invoice, document_number=document_number)
