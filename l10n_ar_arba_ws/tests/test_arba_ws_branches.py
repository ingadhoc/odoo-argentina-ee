import json
from unittest.mock import patch

import requests
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestArbaWsBranches(TransactionCase):
    """A branch with the same CUIT and no CIT of its own uses the A122R credentials (CIT,
    client id and secret, environment) of the nearest company of its fiscal entity with a CIT.
    A branch with another CUIT never does.

        root        CUIT 30697130841  CIT, client id/secret, testing
          ├─ branch CUIT 30697130841  (demo, the default)
          └─ other  CUIT 30500010084  (demo, the default)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cuit_type = cls.env.ref("l10n_ar.it_cuit")
        cls.root = cls._create_company("Root", "30697130841")
        cls.branch = cls._create_company("Branch", "30697130841", parent=cls.root)
        cls.other_cuit = cls._create_company("Other CUIT", "30500010084", parent=cls.root)
        cls.root.write(
            {
                "arba_cit": "root_cit",
                "l10n_ar_arba_client_id": "root_client",
                "l10n_ar_arba_client_secret": "root_secret",
                "l10n_ar_arba_env": "testing",
            }
        )

    @classmethod
    def _create_company(cls, name, cuit, parent=None):
        company = cls.env["res.company"].create({"name": name, "parent_id": parent.id if parent else False})
        company.partner_id.write({"l10n_latam_identification_type_id": cls.cuit_type.id, "vat": cuit})
        return company

    def _get_token_request(self, company):
        """The URL and payload sent to ARBA to get the A122R token of ``company``."""
        sent = {}

        def _fake_request(method, url, **kwargs):
            sent.update(url=url, data=kwargs["data"])
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"access_token": "token", "expires_in": 300}).encode()
            return response

        with patch.object(requests, "request", _fake_request):
            self.env["l10n_ar.afipws.connection"]._l10n_ar_get_token_data(company, "A122R")
        return sent

    def test_branch_uses_the_credentials_of_its_fiscal_entity(self):
        self.assertEqual(self.branch._l10n_ar_arba_ws_company(), self.root)
        self.assertEqual(self.branch._get_arba_ws_environment_type(), "testing")
        sent = self._get_token_request(self.branch)
        self.assertIn("idp.test.arba.gov.ar", sent["url"])
        self.assertIn(
            "client_id=root_client&username=30697130841&password=root_cit&client_secret=root_secret", sent["data"]
        )

    def test_branch_with_its_own_cit_uses_its_own_credentials(self):
        self.branch.write({"arba_cit": "branch_cit", "l10n_ar_arba_env": "production"})
        self.assertEqual(self.branch._l10n_ar_arba_ws_company(), self.branch)
        self.assertEqual(self.branch._get_arba_ws_environment_type(), "production")

    def test_branch_with_another_cuit_never_uses_them(self):
        self.assertEqual(self.other_cuit._l10n_ar_arba_ws_company(), self.other_cuit)
        self.assertEqual(self.other_cuit._get_arba_ws_environment_type(), "demo")

    def test_connection_belongs_to_the_company_of_the_credentials(self):
        companies = []

        def _fake_connection(company, afip_ws):
            companies.append((company, afip_ws, company.env.context.get("l10n_ar_skip_cert_ancestor")))

        with patch.object(type(self.env["res.company"]), "_l10n_ar_get_connection", _fake_connection):
            self.branch._l10n_ar_get_arba_ws_connection()
        self.assertEqual(companies, [(self.root, "A122R", True)])

    def test_branches_report_on_the_ddjj_of_their_fiscal_entity(self):
        self.root.l10n_ar_arba_env = "demo"
        dj_model = self.env["l10n_ar.dj.arba"]
        today = fields.Date.today()
        ddjj = dj_model._ensure_dj(today, self.branch)
        self.assertEqual(ddjj.company_id, self.root)
        self.assertEqual(dj_model._ensure_dj(today, self.root), ddjj, "One DDJJ per fiscal entity and period")
        self.assertEqual(dj_model._ensure_dj(today, self.other_cuit).company_id, self.other_cuit)

    def test_settings_of_a_branch_say_whose_credentials_it_uses(self):
        branch_settings = self.env["res.config.settings"].with_company(self.branch).create({})
        self.assertIn(self.root.name, branch_settings.l10n_ar_arba_ws_shared_msg)
        self.assertFalse(self.env["res.config.settings"].with_company(self.root).create({}).l10n_ar_arba_ws_shared_msg)
        self.assertFalse(
            self.env["res.config.settings"].with_company(self.other_cuit).create({}).l10n_ar_arba_ws_shared_msg
        )
