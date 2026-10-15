##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.l10n_ar_edi.models.res_company import ResCompany as L10nArEdiResCompany
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestArcaLayer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ARS = cls.env.ref("base.ARS")
        cls.USD = cls.env.ref("base.USD")
        cls.EUR = cls.env.ref("base.EUR")
        (cls.ARS | cls.USD | cls.EUR).active = True
        ar_country = cls.env.ref("base.ar")
        cls.company_1 = cls.env["res.company"].create(
            {"name": "AR Company 1", "country_id": ar_country.id, "currency_id": cls.ARS.id}
        )
        cls.company_2 = cls.env["res.company"].create(
            {"name": "AR Company 2", "country_id": ar_country.id, "currency_id": cls.ARS.id}
        )
        (cls.company_1 | cls.company_2).write({"currency_provider": "arca", "currency_interval_unit": "daily"})
        cls.today = cls.company_1._l10n_ar_currency_today()
        cls.today_str = fields.Date.to_string(cls.today)
        cls.yesterday_str = fields.Date.to_string(cls.today - timedelta(days=1))

    def _parse(self, companies, native_result, rate_company=None, context=None):
        """Run the module _parse_arca_data with the native one mocked. Returns the result and the calls made
        to the native method, as (company, env company, currency names)."""
        calls = []

        def fake_native(company, available_currencies):
            calls.append((company, company.env.company, set(available_currencies.mapped("name"))))
            return dict(native_result)

        rate_company = self.company_1 if rate_company is None else rate_company
        with (
            patch.object(type(self.env["res.company"]), "_l10n_ar_get_arca_rate_company", return_value=rate_company),
            patch.object(L10nArEdiResCompany, "_parse_arca_data", autospec=True, side_effect=fake_native),
        ):
            res = companies.with_context(**(context or {}))._parse_arca_data(self.ARS | self.USD | self.EUR)
        return res, calls

    def test_ask_arca_once_with_one_company(self):
        """With several Argentinian companies ARCA is asked once, with the company that has the certificate"""
        _res, calls = self._parse(
            self.company_1 | self.company_2,
            {"USD": (0.001, self.today_str), "ARS": (1.0, self.today_str)},
            rate_company=self.company_2,
        )
        self.assertEqual(len(calls), 1)
        company, env_company, _currencies = calls[0]
        self.assertEqual(company, self.company_2)
        self.assertEqual(env_company, self.company_2)

    def test_skip_currencies_without_arca_code(self):
        """Currencies without ARCA code are not sent to ARCA, so the native error does not stop the update"""
        self.EUR.l10n_ar_afip_code = False
        _res, calls = self._parse(self.company_1, {"USD": (0.001, self.today_str), "ARS": (1.0, self.today_str)})
        currencies = calls[0][2]
        self.assertIn("USD", currencies)
        self.assertNotIn("EUR", currencies)

    def test_only_today_rate(self):
        """A rate that is not today's is not kept, and the sync date is not set"""
        res, _calls = self._parse(
            self.company_1,
            {"USD": (0.001, self.today_str), "EUR": (0.0009, self.yesterday_str), "ARS": (1.0, self.yesterday_str)},
        )
        self.assertEqual(res["USD"], (0.001, self.today_str))
        self.assertNotIn("EUR", res)
        self.assertEqual(res["ARS"], (1.0, self.today_str))
        self.assertFalse(self.company_1.l10n_ar_last_currency_sync_date)

    def test_all_today_sets_sync_date(self):
        self._parse(
            self.company_1 | self.company_2,
            {"USD": (0.001, self.today_str), "EUR": (0.0009, self.today_str), "ARS": (1.0, self.today_str)},
        )
        self.assertEqual(self.company_1.l10n_ar_last_currency_sync_date, self.today)
        self.assertEqual(self.company_2.l10n_ar_last_currency_sync_date, self.today)

    def test_force_create_rate(self):
        """With l10n_ar_force_create_rate the last published rate is kept, dated today"""
        res, _calls = self._parse(
            self.company_1,
            {"USD": (0.001, self.yesterday_str), "ARS": (1.0, self.yesterday_str)},
            context={"l10n_ar_force_create_rate": True},
        )
        self.assertEqual(res["USD"], (0.001, self.today_str))
        self.assertEqual(self.company_1.l10n_ar_last_currency_sync_date, self.today)

    def test_no_company_with_valid_certificate(self):
        res, calls = self._parse(self.company_1, {}, rate_company=self.env["res.company"])
        self.assertFalse(res)
        self.assertFalse(calls)

    def test_existing_rate_not_overwritten(self):
        """A rate already loaded for the day is kept, the native provider would overwrite it"""
        existing = self.env["res.currency.rate"].create(
            {"currency_id": self.USD.id, "name": self.today, "rate": 0.002, "company_id": self.company_1.id}
        )
        self.company_1._generate_currency_rates({"USD": (0.001, self.today_str), "ARS": (1.0, self.today_str)})
        self.assertEqual(existing.rate, 0.002)
        rates = self.env["res.currency.rate"].search(
            [("currency_id", "=", self.USD.id), ("name", "=", self.today), ("company_id", "=", self.company_1.id)]
        )
        self.assertEqual(rates, existing)

    def test_recheck_cron_daily_companies(self):
        """The retry cron only updates the arca companies without today's rate"""
        self.company_2.l10n_ar_last_currency_sync_date = self.today
        updated = self.env["res.company"]

        def fake_update(companies):
            nonlocal updated
            updated |= companies
            return True

        with patch.object(
            type(self.env["res.company"]), "update_currency_rates", autospec=True, side_effect=fake_update
        ):
            self.env["res.company"].re_check_arca_currency_rate()
        self.assertIn(self.company_1, updated)
        self.assertNotIn(self.company_2, updated)
