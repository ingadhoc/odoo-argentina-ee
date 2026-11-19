from unittest.mock import patch

from odoo.addons.l10n_ar_edi.models.l10n_ar_afipws_connection import ARTransport
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open


@tagged("post_install", "-at_install")
class TestWsdlCache(TransactionCase):
    """The ARCA WSDL is kept in the per-company ORM cache, like upstream master does."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        ar_country = cls.env.ref("base.ar")
        ar_currency = cls.env.ref("base.ARS")
        afip_ri = cls.env.ref("l10n_ar.res_IVARI")

        cls.company = cls.env["res.company"].create(
            {"name": "Test WSDL Cache Company", "currency_id": ar_currency.id, "country_id": ar_country.id}
        )
        cls.company.partner_id.write(
            {
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

    def setUp(self):
        super().setUp()
        # the zeep cache lives in the ORM cache, which is not rolled back between tests
        zeep_cache = self.company._get_zeep_cache__()
        zeep_cache.clear()
        self.addCleanup(zeep_cache.clear)

    def _patch_wsdl_download(self, content=None):
        """Serve the schema file upstream uses in its own tests, without leaving the test."""

        def load_remote_data(transport, url):
            if content is not None:
                return content
            service = url.rpartition("/")[2].partition("?")[0]
            with file_open(f"l10n_ar_edi/tests/expected_requests/{service}-schema.xml", "rb") as fd:
                return fd.read()

        return patch.object(ARTransport, "_load_remote_data", autospec=True, side_effect=load_remote_data)

    def test_05_wsdl_downloaded_once(self):
        """Only the first client downloads the WSDL, the next ones take it from the company cache."""
        wsdl = self.connection._l10n_ar_get_afip_ws_url("wsfe", "testing")
        with self._patch_wsdl_download() as load_remote_data:
            self.connection._get_client()
            self.connection._get_client()

        load_remote_data.assert_called_once()
        self.assertEqual(load_remote_data.call_args.args[1], wsdl)

    def test_10_invalid_wsdl_not_cached(self):
        """An invalid WSDL (e.g. a maintenance page with HTTP 200) is not kept in the cache."""
        wsdl = self.connection._l10n_ar_get_afip_ws_url("wsfe", "testing")
        with (
            self._patch_wsdl_download(b"Service under maintenance"),
            self.assertRaisesRegex(UserError, "There was a problem with the connection to the wsfe webservice"),
        ):
            self.connection._get_client()

        self.assertNotIn(wsdl, self.company._get_zeep_cache__())

    def test_15_cache_is_keyed_by_webservice_url(self):
        """Each webservice has its own WSDL: caching one must not serve another."""
        with self._patch_wsdl_download() as load_remote_data:
            self.connection._get_client()
            self.connection_wsfex._get_client()
            self.connection._get_client()

        urls = [call.args[1] for call in load_remote_data.call_args_list]
        self.assertEqual(len(urls), 2, "wsfe and wsfex must be downloaded once each")
        self.assertEqual(len(set(urls)), 2, "The two downloads must correspond to two different URLs")

    def test_20_credentials_are_never_cached(self):
        """Only the WSDL document is cached: token and sign are read on every call."""
        with self._patch_wsdl_download() as load_remote_data:
            __, auth = self.connection._get_client()
            self.assertEqual(auth["Token"], "mock-afip-token")
            self.assertEqual(auth["Sign"], "mock-afip-sign")

            self.connection.write({"token": "rotated-token", "sign": "rotated-sign"})
            __, auth = self.connection._get_client()

        self.assertEqual(auth["Token"], "rotated-token", "The token must be re-read, not cached with the WSDL")
        self.assertEqual(auth["Sign"], "rotated-sign", "The sign must be re-read, not cached with the WSDL")
        load_remote_data.assert_called_once()
