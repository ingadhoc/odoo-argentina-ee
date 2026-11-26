from unittest.mock import MagicMock, patch

from odoo.addons.l10n_ar_edi_ux.models.l10n_ar_afipws_connection import ARCA_UNAVAILABLE, ARCA_UNCONFIRMED
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    ConnectTimeout,
    HTTPError,
    ReadTimeout,
)
from urllib3.exceptions import MaxRetryError, NewConnectionError, ProtocolError
from zeep.exceptions import TransportError


@tagged("post_install", "-at_install")
class TestArcaUnavailable(TransactionCase):
    """ARCA transport failures must show a clear message, never the raw HTTP error or URL."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection = cls.env["l10n_ar.afipws.connection"]

    @staticmethod
    def _http_error(status):
        response = MagicMock(status_code=status, url="https://servicios1.afip.gov.ar/wsfev1/service.asmx")
        return HTTPError(f"{status} Server Error for url: {response.url}", response=response)

    @staticmethod
    def _connect_failure():
        return RequestsConnectionError(
            MaxRetryError(None, "https://servicios1.afip.gov.ar", NewConnectionError(None, "x"))
        )

    @staticmethod
    def _connection_dropped():
        return RequestsConnectionError(ProtocolError("Connection aborted.", ConnectionResetError("reset")))

    def test_05_classification_before_sending(self):
        """Fetching the WSDL or the token: any transport failure means ARCA is not available."""
        for error in (
            self._http_error(500),
            self._http_error(503),
            self._connect_failure(),
            self._connection_dropped(),
            ReadTimeout("timed out"),
        ):
            with self.subTest(error=repr(error)):
                self.assertEqual(self.connection._l10n_ar_arca_error_kind(error), ARCA_UNAVAILABLE)

    def test_10_classification_after_sending(self):
        """After sending the CAE request, only failures where the request never left mean it was not processed."""
        kind = lambda error: self.connection._l10n_ar_arca_error_kind(error, request_sent=True)  # noqa: E731
        self.assertEqual(kind(self._http_error(503)), ARCA_UNAVAILABLE)
        self.assertEqual(kind(TransportError(status_code=503)), ARCA_UNAVAILABLE)
        self.assertEqual(kind(self._connect_failure()), ARCA_UNAVAILABLE)
        self.assertEqual(kind(ConnectTimeout(MaxRetryError(None, "x"))), ARCA_UNAVAILABLE)
        self.assertEqual(kind(ReadTimeout("timed out")), ARCA_UNCONFIRMED)
        self.assertEqual(kind(self._connection_dropped()), ARCA_UNCONFIRMED)

    def test_15_other_errors_are_not_arca_down(self):
        """Odoo errors and client errors must not be presented as an ARCA outage."""
        for error in (self._http_error(404), TransportError(status_code=400), ValueError("x"), UserError("x")):
            with self.subTest(error=repr(error)):
                self.assertIsNone(self.connection._l10n_ar_arca_error_kind(error, request_sent=True))

    def test_20_connection_error_hides_technical_detail(self):
        with self.assertRaises(UserError) as ctx:
            self.connection._l10n_ar_process_connection_error(self._http_error(503), "production", "wsfe")
        message = ctx.exception.args[0]
        self.assertIn("ARCA is not available", message)
        self.assertNotIn("503", message)
        self.assertNotIn("afip.gov.ar", message)

    def test_25_unrelated_connection_error_keeps_upstream_behaviour(self):
        with self.assertRaises(UserError) as ctx:
            self.connection._l10n_ar_process_connection_error(
                ValueError("Computador no autorizado a acceder al servicio"), "production", "wsfe"
            )
        self.assertNotIn("ARCA is not available", ctx.exception.args[0])

    def test_30_cae_request_timeout_does_not_ask_to_retry_blindly(self):
        move = self.env["account.move"].new({})
        path = "odoo.addons.l10n_ar_edi.models.account_move.AccountMove._l10n_ar_do_afip_ws_request_cae"
        with patch(path, side_effect=ReadTimeout("timed out")):
            with self.assertRaises(UserError) as ctx:
                move._l10n_ar_do_afip_ws_request_cae(None, None, None)
        message = ctx.exception.args[0]
        self.assertIn("ARCA did not confirm the authorization", message)
        self.assertIn("do not validate it again", message)

    def test_35_cae_request_service_down_is_not_unconfirmed(self):
        move = self.env["account.move"].new({})
        path = "odoo.addons.l10n_ar_edi.models.account_move.AccountMove._l10n_ar_do_afip_ws_request_cae"
        with patch(path, side_effect=self._http_error(503)):
            with self.assertRaises(UserError) as ctx:
                move._l10n_ar_do_afip_ws_request_cae(None, None, None)
        self.assertIn("ARCA is not available", ctx.exception.args[0])

    def test_40_cae_request_unrelated_error_is_reraised(self):
        move = self.env["account.move"].new({})
        path = "odoo.addons.l10n_ar_edi.models.account_move.AccountMove._l10n_ar_do_afip_ws_request_cae"
        with patch(path, side_effect=self._http_error(404)):
            with self.assertRaises(HTTPError):
                move._l10n_ar_do_afip_ws_request_cae(None, None, None)
