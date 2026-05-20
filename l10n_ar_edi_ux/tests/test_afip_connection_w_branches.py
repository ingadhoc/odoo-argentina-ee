import base64
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open


@tagged("post_install", "-at_install")
class TestAfipConnection(TransactionCase):
    """Tests for the ARCA/AFIP connection extensions added by l10n_ar_edi_ux.

    Covers two related features:
    - _l10n_ar_get_connection: branch companies without a certificate delegate
      ARCA token generation to the nearest ancestor that shares the same CUIT
      and holds a certificate.  Multi-level hierarchies are supported.
    - _check_match_between_certificate_and_company: raises a clear UserError when
      the CUIT embedded in the certificate subject differs from the company's CUIT.

    Hierarchy under test:

        parent_company          CUIT 20313932975  HAS certificate   (grandparent)
          ├─ child_company      CUIT 20313932975  no certificate    (child / invoicing company)
          │    └─ grandchild_company   no CUIT    no certificate    (grandchild)
          ├─ branch_diff_cuit   CUIT 30711017077  no certificate    (sibling, different CUIT)
          ├─ branch_no_cuit     no CUIT           no certificate    (sibling, no CUIT)
          └─ branch_with_cert   CUIT 30500010084  HAS certificate   (sibling, different CUIT, own cert)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        ar_country = cls.env.ref("base.ar")
        ar_currency = cls.env.ref("base.ARS")
        cuit_type = cls.env.ref("l10n_ar.it_cuit")
        afip_ri = cls.env.ref("l10n_ar.res_IVARI")

        # Shared private key (satisfies the certificate FK)
        cls.ar_key = cls.env["certificate.key"].create(
            {
                "name": "Test RSA Key",
                "content": base64.b64encode(file_open("l10n_ar_edi/tests/private_key.pem", "rb").read()),
            }
        )

        # test_cert1.crt has serialNumber = "CUIT 20313932975"
        cls.ar_certificate = cls.env["certificate.certificate"].create(
            {
                "name": "Test Cert (CUIT 20313932975)",
                "content": base64.b64encode(file_open("l10n_ar_edi/tests/test_cert1.crt", "rb").read()),
                "private_key_id": cls.ar_key.id,
            }
        )

        # ---------- parent company: has certificate, CUIT 20313932975 ----------
        cls.parent_company = cls.env["res.company"].create(
            {"name": "Test Parent Company", "currency_id": ar_currency.id, "country_id": ar_country.id}
        )
        cls.parent_company.partner_id.write(
            {
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "20313932975",
                "l10n_ar_afip_responsibility_type_id": afip_ri.id,
                "country_id": ar_country.id,
            }
        )
        cls.parent_company.write(
            {
                "l10n_ar_afip_ws_environment": "testing",
                "l10n_ar_afip_ws_crt_id": cls.ar_certificate.id,
            }
        )

        # ---------- child: same CUIT as parent, no certificate ----------
        cls.child_company = cls.env["res.company"].create(
            {
                "name": "Test Branch 1 (same CUIT no Cert)",
                "parent_id": cls.parent_company.id,
                "currency_id": ar_currency.id,
                "country_id": ar_country.id,
            }
        )
        cls.child_company.partner_id.write(
            {
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "20313932975",
                "l10n_ar_afip_responsibility_type_id": afip_ri.id,
                "country_id": ar_country.id,
            }
        )
        cls.child_company.write({"l10n_ar_afip_ws_environment": "testing"})

        # ---------- grandchild: no CUIT, no certificate, parent = child ----------
        cls.grandchild_company = cls.env["res.company"].create(
            {
                "name": "Test Grandchild Branch (no CUIT)",
                "parent_id": cls.child_company.id,
                "currency_id": ar_currency.id,
                "country_id": ar_country.id,
            }
        )
        # partner intentionally left without CUIT
        cls.grandchild_company.write({"l10n_ar_afip_ws_environment": "testing"})

        # ---------- sibling without CUIT: no certificate ----------
        cls.branch_no_cuit = cls.env["res.company"].create(
            {
                "name": "Test Branch 3 (No CUIT no Cert)",
                "parent_id": cls.parent_company.id,
                "currency_id": ar_currency.id,
                "country_id": ar_country.id,
            }
        )
        # partner intentionally left without CUIT
        cls.branch_no_cuit.write({"l10n_ar_afip_ws_environment": "testing"})

        # ---------- sibling with a different CUIT: no certificate ----------
        cls.branch_diff_cuit = cls.env["res.company"].create(
            {
                "name": "TestBranch 2 (Diff CUIT no Cert)",
                "parent_id": cls.parent_company.id,
                "currency_id": ar_currency.id,
                "country_id": ar_country.id,
            }
        )
        cls.branch_diff_cuit.partner_id.write(
            {
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "30711017077",
                "l10n_ar_afip_responsibility_type_id": afip_ri.id,
                "country_id": ar_country.id,
            }
        )
        cls.branch_diff_cuit.write({"l10n_ar_afip_ws_environment": "testing"})

        # ---------- sibling with a different CUIT: HAS its own certificate ----------
        cls.branch_with_cert = cls.env["res.company"].create(
            {
                "name": "Test Branch 4 (Diff CUIT Own Cert)",
                "parent_id": cls.parent_company.id,
                "currency_id": ar_currency.id,
                "country_id": ar_country.id,
            }
        )
        cls.branch_with_cert.partner_id.write(
            {
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "30500010084",
                "l10n_ar_afip_responsibility_type_id": afip_ri.id,
                "country_id": ar_country.id,
            }
        )
        cls.branch_with_cert.write(
            {
                "l10n_ar_afip_ws_environment": "testing",
                "l10n_ar_afip_ws_crt_id": cls.ar_certificate.id,
            }
        )

        # ---------- companies for certificate CUIT validation ----------
        cls.company_matching = cls.env["res.company"].create(
            {"name": "Company CUIT Matches Cert", "currency_id": ar_currency.id, "country_id": ar_country.id}
        )
        cls.company_matching.partner_id.write(
            {
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "20313932975",
                "l10n_ar_afip_responsibility_type_id": afip_ri.id,
                "country_id": ar_country.id,
            }
        )
        cls.company_matching.write({"l10n_ar_afip_ws_crt_id": cls.ar_certificate.id})

        cls.company_mismatch = cls.env["res.company"].create(
            {"name": "Company CUIT Mismatches Cert", "currency_id": ar_currency.id, "country_id": ar_country.id}
        )
        cls.company_mismatch.partner_id.write(
            {
                "l10n_latam_identification_type_id": cuit_type.id,
                "vat": "30711017077",
                "l10n_ar_afip_responsibility_type_id": afip_ri.id,
                "country_id": ar_country.id,
            }
        )
        cls.company_mismatch.write({"l10n_ar_afip_ws_crt_id": cls.ar_certificate.id})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _mock_token_generation(self):
        """Patch _l10n_ar_get_token_data to avoid real AFIP network calls.

        Yields a list that is populated with every ``company`` argument received
        by the patched method, so tests can assert which company's certificate
        was used for token generation.

        A regular function (not a Mock) is used as the replacement so that
        Python's descriptor protocol correctly binds the connection record as
        ``self`` — ensuring the ``company`` argument is captured at the right
        position.
        """
        now = fields.Datetime.now()
        fake_token = {
            "token": "mock-afip-token",
            "sign": "mock-afip-sign",
            "generation_time": now,
            "expiration_time": now + timedelta(hours=12),
        }
        companies_used = []

        def _fake_get_token_data(self_conn, company, afip_ws):
            companies_used.append(company)
            return fake_token

        AfipwsConnectionCls = type(self.env["l10n_ar.afipws.connection"])
        with patch.object(AfipwsConnectionCls, "_l10n_ar_get_token_data", _fake_get_token_data):
            yield companies_used

    def _get_connection(self, company, afip_ws="wsfe"):
        """Thin wrapper that skips the DB commit injected by the base method."""
        return company.with_context(l10n_ar_invoice_skip_commit=True)._l10n_ar_get_connection(afip_ws)

    # ------------------------------------------------------------------
    # _l10n_ar_get_connection tests
    # ------------------------------------------------------------------

    def test_05_child_generates_token_using_parent_certificate(self):
        """Invoicing from Child (same CUIT, no cert) must use Parent's certificate.

        When no pre-existing connection exists the base method calls
        _l10n_ar_get_token_data to create a fresh AFIP token.  The override
        must route that call to parent_company (the ancestor with the cert),
        and the resulting connection record must be stored under parent_company.

        Hierarchy:
          parent_company  (CUIT 20313932975, cert)
            └─ child_company  (CUIT 20313932975, no cert)   ← invoicing company
        """
        with self._mock_token_generation() as companies_used:
            connection = self._get_connection(self.child_company)

        self.assertEqual(len(companies_used), 1, "Exactly one token request expected")
        self.assertEqual(
            companies_used[0],
            self.parent_company,
            "Token must be generated using parent_company's certificate, not child's",
        )
        self.assertEqual(
            connection.company_id,
            self.parent_company,
            "The created connection must be owned by parent_company",
        )
        self.assertEqual(connection.token, "mock-afip-token")

    def test_10_branch_diff_cuit_wo_cert_raise_when_generates_own_token(self):
        """Branch with a different CUIT and no certificate must raise a UserError.

        branch_diff_cuit has a CUIT that differs from every ancestor's CUIT, so
        _l10n_ar_get_cert_ancestor() returns empty.  The override must raise
        early with a descriptive message before any token generation is attempted.

        Hierarchy:
          parent_company     (CUIT 20313932975, cert)
            └─ branch_diff_cuit  (CUIT 30711017077, no cert)   ← this company
        """
        with self._mock_token_generation() as companies_used:
            with self.assertRaises(UserError) as ctx:
                self._get_connection(self.branch_diff_cuit)

        error_message = str(ctx.exception)
        self.assertIn(self.branch_diff_cuit.name, error_message)
        self.assertEqual(
            companies_used,
            [],
            "No token must be requested when no cert ancestor exists for the company's CUIT",
        )

    def test_15_branch_with_own_cert_uses_own_certificate(self):
        """Branch that holds its own certificate must NOT delegate to the parent.

        The override condition ``not self.sudo().l10n_ar_afip_ws_crt_id`` is False
        when the branch already has a certificate, so _l10n_ar_get_connection
        falls straight through to the standard super() path and generates the
        token for the branch itself — never for parent_company.

        Hierarchy:
          parent_company       (CUIT 20313932975, cert)
            └─ branch_with_cert  (CUIT 30711017077, HAS own cert)   ← invoicing company
        """
        with self._mock_token_generation() as companies_used:
            connection = self._get_connection(self.branch_with_cert)

        self.assertEqual(len(companies_used), 1)
        self.assertEqual(
            companies_used[0],
            self.branch_with_cert,
            "Token must be generated using branch_with_cert's own certificate, " "not delegated to parent_company",
        )
        self.assertEqual(connection.company_id, self.branch_with_cert)

    def test_20_branch_no_cuit_raises_before_token_request(self):
        """Grandchild without CUIT must raise a UserError before any token is requested.

        When a branch has no CUIT it is impossible to find a matching ancestor;
        _l10n_ar_get_connection must raise early with a message that identifies
        the company and explains the missing data.

        Hierarchy:
          parent_company  (CUIT 20313932975, cert)
            └─ child_company  (CUIT 20313932975, no cert)
                 └─ grandchild_company  (no CUIT, no cert)   ← this company
        """
        with self._mock_token_generation() as companies_used:
            with self.assertRaises(UserError) as ctx:
                self._get_connection(self.grandchild_company)

        error_message = str(ctx.exception)
        self.assertIn(self.grandchild_company.name, error_message)
        self.assertIn("CUIT", error_message)
        self.assertEqual(
            companies_used,
            [],
            "No token must be requested when the company has no CUIT",
        )

    def test_25_branch_sibling_no_cuit_raises_before_token_request(self):
        """Sibling branch without CUIT must raise a UserError before any token is requested.

        Even though the parent holds a certificate, the branch has no CUIT so
        _l10n_ar_get_cert_ancestor() cannot find a matching ancestor.
        _l10n_ar_get_connection must raise early and never attempt token generation.

        Hierarchy:
          parent_company  (CUIT 20313932975, cert)
            ├─ child_company   (CUIT 20313932975, no cert)
            └─ branch_no_cuit  (no CUIT, no cert)   ← this company
        """
        with self._mock_token_generation() as companies_used:
            with self.assertRaises(UserError) as ctx:
                self._get_connection(self.branch_no_cuit)

        error_message = str(ctx.exception)
        self.assertIn(self.branch_no_cuit.name, error_message)
        self.assertIn("CUIT", error_message)
        self.assertEqual(
            companies_used,
            [],
            "No token must be requested when the sibling branch has no CUIT",
        )

    def test_30_three_level_hierarchy_token_generated_for_grandparent(self):
        """3-level hierarchy: grandchild (same CUIT, no cert) skips intermediate
        (no cert) and generates the token using grandparent's certificate.

        This test validates the _l10n_ar_get_cert_ancestor() helper that walks
        the full parent chain.  Without it, the delegation to the intermediate
        would bypass the edi_ux override and the token would be (incorrectly)
        requested with the intermediate company which has no cert.

        Hierarchy:
          parent_company          (CUIT A, cert)       <- grandparent with cert
            └─ child_company      (CUIT A, no cert)    <- intermediate, no cert
                 └─ grandchild_same_cuit  (CUIT A, no cert)   <- invoicing company
        """
        grandchild_same_cuit = self.env["res.company"].create(
            {
                "name": "Grandchild Same CUIT",
                "parent_id": self.child_company.id,
                "currency_id": self.env.ref("base.ARS").id,
                "country_id": self.env.ref("base.ar").id,
            }
        )
        grandchild_same_cuit.partner_id.write(
            {
                "l10n_latam_identification_type_id": self.env.ref("l10n_ar.it_cuit").id,
                "vat": "20313932975",
                "l10n_ar_afip_responsibility_type_id": self.env.ref("l10n_ar.res_IVARI").id,
                "country_id": self.env.ref("base.ar").id,
            }
        )
        grandchild_same_cuit.write({"l10n_ar_afip_ws_environment": "testing"})

        with self._mock_token_generation() as companies_used:
            connection = self._get_connection(grandchild_same_cuit)

        self.assertEqual(len(companies_used), 1)
        self.assertEqual(
            companies_used[0],
            self.parent_company,
            "Token must be generated for grandparent (the ancestor with the cert), "
            "not the intermediate child which has no cert",
        )
        self.assertEqual(
            connection.company_id,
            self.parent_company,
            "Connection must be owned by the grandparent, not the intermediate",
        )

    # ------------------------------------------------------------------
    # _check_match_between_certificate_and_company tests
    # ------------------------------------------------------------------

    def test_35_check_certificate_match_does_not_raise(self):
        """When company CUIT equals certificate CUIT no UserError is raised."""
        try:
            self.company_matching._check_match_between_certificate_and_company()
        except UserError as exc:
            self.fail(f"Unexpected UserError for matching CUITs: {exc}")

    def test_40_check_certificate_mismatch_raises_user_error(self):
        """When company CUIT differs from certificate CUIT a UserError is raised
        with both CUITs in the message."""
        with self.assertRaises(UserError) as ctx:
            self.company_mismatch._check_match_between_certificate_and_company()

        error_message = str(ctx.exception)
        self.assertIn("CUIT 20313932975", error_message)
        self.assertIn("30711017077", error_message)
