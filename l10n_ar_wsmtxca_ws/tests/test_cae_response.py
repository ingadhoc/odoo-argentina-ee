"""What the module does with what ARCA answers.

_l10n_ar_do_afip_ws_request_cae takes the client, the ticket and the transport
as arguments, so the response handling can be exercised by handing it a stand-in
for the three -- no connection is patched and no network is reached. What is
faked is the transport, never the code under test.
"""

from types import SimpleNamespace

from odoo.tests import tagged

from .common import TestWsmtxcaCommon

FAKE_AUTH = {"Token": "a-token", "Sign": "a-sign", "Cuit": "30111111118"}
FAKE_CAE = "70417054367476"


def code_description(code, description):
    return SimpleNamespace(codigo=code, descripcion=description)


class FakeService(dict):
    """client.service[ws_method] -- returns the canned response."""

    def __init__(self, response):
        super().__init__()
        self.response = response

    def __getitem__(self, _ws_method):
        return lambda *args, **kwargs: self.response


class FakeClient:
    """Stand-in for the zeep client: builds the array types and answers the call."""

    def __init__(self, response):
        self.service = FakeService(response)
        # _ws_verify_request_data validates the payload against the WSDL through
        # this private attribute; with no WSDL at hand it is a no-op here.
        self._Client__obj = SimpleNamespace(service=None, create_message=lambda *args, **kwargs: None)

    @staticmethod
    def get_type(_type_name):
        return lambda argument: argument


def arca_response(resultado="A", cae=FAKE_CAE, errors=None, observations=None, event=None):
    """A wsmtxca autorizarComprobante response, shaped like zeep returns it."""
    return SimpleNamespace(
        resultado=resultado,
        comprobanteResponse=SimpleNamespace(CAE=cae, fechaVencimientoCAE="2026-12-31") if cae else None,
        arrayErrores=SimpleNamespace(codigoDescripcion=errors) if errors else None,
        arrayObservaciones=SimpleNamespace(codigoDescripcion=observations) if observations else None,
        evento=event,
    )


@tagged("post_install", "post_install_l10n", "-at_install", *TestWsmtxcaCommon.extra_tags)
class TestWsmtxcaCaeResponse(TestWsmtxcaCommon):
    def _invoice_awaiting_cae(self, document_number="12345-12345678"):
        """A posted invoice with the local authorization cleared, so the module
        treats it as still pending at ARCA."""
        invoice = self._create_invoice_ar()
        self._post(invoice)
        invoice.l10n_latam_document_number = document_number
        invoice.sudo().write({"l10n_ar_afip_auth_code": False, "l10n_ar_afip_auth_mode": False})
        return invoice.with_context(l10n_ar_invoice_skip_commit=True)

    def _request_cae(self, invoice, response):
        transport = SimpleNamespace(xml_request="<request/>", xml_response="<response/>")
        return invoice._l10n_ar_do_afip_ws_request_cae(FakeClient(response), FAKE_AUTH, transport)

    def test_wsmtxca_authorized_invoice_keeps_the_cae(self):
        """Task 68095: an authorized answer lands on the invoice -- code, due
        date, result and both XML payloads.

        Covers behaviour 30 of the survey.
        """
        invoice = self._invoice_awaiting_cae()

        return_info = self._request_cae(invoice, arca_response())

        self.assertFalse(return_info, "an authorized invoice reports no error back")
        self.assertEqual(invoice.l10n_ar_afip_auth_mode, "CAE")
        self.assertEqual(invoice.l10n_ar_afip_auth_code, FAKE_CAE)
        self.assertEqual(invoice.l10n_ar_afip_result, "A")
        self.assertEqual(invoice.l10n_ar_afip_xml_request, "<request/>")
        self.assertEqual(invoice.l10n_ar_afip_xml_response, "<response/>")

    def test_wsmtxca_observed_invoice_reports_the_observations(self):
        """Task 68095: an observed answer is still an authorization -- the CAE is
        kept and the observations reach the chatter.

        Covers behaviours 30 and 32 of the survey.
        """
        invoice = self._invoice_awaiting_cae()
        messages_before = len(invoice.message_ids)

        self._request_cae(
            invoice,
            arca_response(resultado="O", observations=[code_description(10192, "Se aceptó con observaciones")]),
        )

        self.assertEqual(invoice.l10n_ar_afip_auth_code, FAKE_CAE)
        self.assertEqual(invoice.l10n_ar_afip_result, "O")
        self.assertGreater(len(invoice.message_ids), messages_before, "the observations were not posted")
        self.assertIn("10192", invoice.message_ids[0].body)

    def test_wsmtxca_rejected_invoice_gets_no_cae(self):
        """Task 68095: a rejected answer leaves the invoice without a CAE, keeps
        the XML for diagnosis and hands the error message back to the caller.

        Covers behaviour 31 of the survey.
        """
        invoice = self._invoice_awaiting_cae()

        return_info = self._request_cae(
            invoice, arca_response(resultado="R", cae=None, errors=[code_description(10016, "Comprobante rechazado")])
        )

        self.assertTrue(return_info, "a rejected invoice must hand the error back to the caller")
        self.assertIn("10016", return_info)
        self.assertFalse(invoice.l10n_ar_afip_auth_code, "a rejected invoice must not keep a CAE")
        self.assertEqual(invoice.l10n_ar_afip_xml_response, "<response/>")

    def test_wsmtxca_leaves_other_webservices_alone(self):
        """Task 68095: an invoice on another webservice is not touched by the
        wsmtxca branch.

        Covers behaviour 33 of the survey.
        """
        wsfe_journal = self._create_journal("wsfe", data={"code": "WSFE1"})
        invoice = self._create_invoice_ar(journal_id=wsfe_journal)
        self._post(invoice)
        cae_before = invoice.l10n_ar_afip_auth_code

        # The wsmtxca handler must delegate and leave the invoice as it found it
        self._request_cae(invoice.with_context(l10n_ar_invoice_skip_commit=True), arca_response())

        self.assertEqual(invoice.l10n_ar_afip_auth_code, cae_before)
