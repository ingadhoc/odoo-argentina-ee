from contextlib import contextmanager
from unittest.mock import patch

from odoo.addons.l10n_ar_edi.models import l10n_ar_afipws_connection as edi_connection
from odoo.addons.l10n_ar_edi_ux.models.l10n_ar_afipws_connection import (
    DEFAULT_WSDL_CACHE_TTL,
    WSDL_CACHE_TTL_PARAM,
)
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open
from odoo.tools.zeep import Transport
from zeep.cache import InMemoryCache


@tagged("post_install", "-at_install")
class TestWsdlCache(TransactionCase):
    """Tests for the ARCA WSDL cache added by l10n_ar_edi_ux.

    They exist mostly as a guard: the override copies the body of upstream's
    ``_get_client()``, so the day Odoo changes that method the module keeps working
    but silently goes back to downloading the WSDL once per invoice.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        ar_country = cls.env.ref("base.ar")
        ar_currency = cls.env.ref("base.ARS")
        cuit_type = cls.env.ref("l10n_ar.it_cuit")
        afip_ri = cls.env.ref("l10n_ar.res_IVARI")

        cls.company = cls.env["res.company"].create(
            {"name": "Test WSDL Cache Company", "currency_id": ar_currency.id, "country_id": ar_country.id}
        )
        cls.company.partner_id.write(
            {
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "20313932975",
                "l10n_ar_afip_responsibility_type_id": afip_ri.id,
                "country_id": ar_country.id,
            }
        )
        cls.company.write({"l10n_ar_afip_ws_environment": "testing"})

        cls.connection = cls.env["l10n_ar.afipws.connection"].create(
            {
                "company_id": cls.company.id,
                "type": "testing",
                "l10n_ar_afip_ws": "wsfe",
                "token": "mock-afip-token",
                "sign": "mock-afip-sign",
            }
        )
        cls.connection_wsfex = cls.env["l10n_ar.afipws.connection"].create(
            {
                "company_id": cls.company.id,
                "type": "testing",
                "l10n_ar_afip_ws": "wsfex",
                "token": "mock-afip-token",
                "sign": "mock-afip-sign",
            }
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _mock_wsdl_download(self):
        """Patch ARTransport so no request leaves the test, and count WSDL downloads.

        The replacement only overrides ``_load_remote_data``, the hook zeep calls when it
        misses the cache, and serves the same schema file upstream uses in its own mocked
        tests.  It is patched on the ``l10n_ar_edi`` module because that is the attribute
        both the override and ``super()`` resolve at runtime.

        Yields the list of downloaded URLs, so tests can count them.
        """
        downloads = []

        class CountingTransport(Transport):
            def _load_remote_data(self, url):
                downloads.append(url)
                service = url.rpartition("/")[2].partition("?")[0]
                with file_open(f"l10n_ar_edi/tests/expected_requests/{service}-schema.xml", "rb") as fd:
                    return fd.read()

        # InMemoryCache._cache is a dict on the class, shared by the whole process.
        # Without a fresh one per test the mocked WSDL leaks into - and out of - any
        # other test that builds a client.
        with patch.object(InMemoryCache, "_cache", {}):
            with patch.object(edi_connection, "ARTransport", CountingTransport):
                yield downloads

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_05_wsdl_is_downloaded_once_by_default(self):
        """With no system parameter set, the second _get_client() must not download again."""
        self.assertFalse(
            self.env["ir.config_parameter"].sudo().get_param(WSDL_CACHE_TTL_PARAM),
            "This test asserts the out of the box behaviour, the parameter must not be set",
        )
        self.assertGreater(DEFAULT_WSDL_CACHE_TTL, 0, "The default TTL must keep the cache enabled")

        with self._mock_wsdl_download() as downloads:
            self.connection._get_client()
            after_first = len(downloads)
            self.connection._get_client()

            self.assertEqual(after_first, 1, "The first client must download the WSDL exactly once")
            self.assertEqual(
                len(downloads),
                after_first,
                "The second client must be built from the cached WSDL, without downloading it again",
            )

    def test_10_ttl_zero_restores_native_behaviour(self):
        """The kill switch: with the parameter at 0 the WSDL is downloaded on every call."""
        self.env["ir.config_parameter"].sudo().set_param(WSDL_CACHE_TTL_PARAM, "0")

        with self._mock_wsdl_download() as downloads:
            self.connection._get_client()
            self.connection._get_client()

            self.assertEqual(
                len(downloads),
                2,
                "With the cache disabled each call must go back to downloading the WSDL",
            )

    def test_15_cache_is_keyed_by_webservice_url(self):
        """Each webservice has its own WSDL: caching one must not serve another."""
        self.env["ir.config_parameter"].sudo().set_param(WSDL_CACHE_TTL_PARAM, "300")

        with self._mock_wsdl_download() as downloads:
            self.connection._get_client()
            self.connection_wsfex._get_client()
            self.connection._get_client()

            self.assertEqual(len(downloads), 2, "wsfe and wsfex must be downloaded once each")
            self.assertEqual(
                len(set(downloads)),
                2,
                "The two downloads must correspond to two different URLs",
            )

    def test_20_credentials_are_never_cached(self):
        """Only the WSDL document is cached: token and sign are read on every call."""
        self.env["ir.config_parameter"].sudo().set_param(WSDL_CACHE_TTL_PARAM, "300")

        with self._mock_wsdl_download() as downloads:
            __, auth = self.connection._get_client()
            self.assertEqual(auth["Token"], "mock-afip-token")
            self.assertEqual(auth["Sign"], "mock-afip-sign")

            self.connection.write({"token": "rotated-token", "sign": "rotated-sign"})
            __, auth = self.connection._get_client()

            self.assertEqual(auth["Token"], "rotated-token", "The token must be re-read, not cached with the WSDL")
            self.assertEqual(auth["Sign"], "rotated-sign", "The sign must be re-read, not cached with the WSDL")
            self.assertEqual(len(downloads), 1, "Rotating the credentials must not force a new WSDL download")
