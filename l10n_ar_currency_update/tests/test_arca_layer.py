##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta
from odoo import fields
from odoo.addons.currency_rate_live.models.res_config_settings import ResCompany as CurrencyRateLiveResCompany
from odoo.addons.l10n_ar_edi.models.res_company import ResCompany as L10nArEdiResCompany
from odoo.addons.l10n_ar_edi.models.res_currency import ResCurrency as L10nArEdiResCurrency
from odoo.exceptions import UserError
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
        # The sync date is marked only when every active currency with ARCA code has today's rate
        cls.arca_currencies = cls.env["res.currency"].search([("l10n_ar_afip_code", "!=", False)]) - cls.ARS

    def _parse(self, companies, arca_result, rate_company=None, context=None, currencies=None, connection_error=None):
        """Run the module _parse_arca_data with ARCA mocked. arca_result maps each currency name to the
        (rate, date) expected in the parsed data, or to an exception to raise. Returns the result and the
        calls made, as (company of the connection, currency name)."""
        calls = []
        connected = []

        def fake_connection(company, afip_ws):
            if connection_error:
                raise connection_error
            connected.append(company)
            connection = MagicMock()
            connection._get_client.return_value = ("client", "auth")
            return connection

        def fake_rate(currency, client, auth, afip_ws="wsfe", date_rate=None):
            calls.append((connected[-1], currency.name))
            value = arca_result.get(currency.name)
            if isinstance(value, Exception):
                raise value
            if not value:
                return None, False
            rate, date = value
            # ARCA returns the day before the one the rate is used for, and ARS per unit
            arca_date = datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)
            return arca_date.strftime("%Y%m%d"), 1.0 / rate

        rate_company = self.company_1 if rate_company is None else rate_company
        currencies = (self.ARS | self.USD | self.EUR) if currencies is None else currencies
        with (
            patch.object(type(self.env["res.company"]), "_l10n_ar_get_arca_rate_company", return_value=rate_company),
            patch.object(L10nArEdiResCompany, "_l10n_ar_get_connection", autospec=True, side_effect=fake_connection),
            patch.object(
                L10nArEdiResCurrency, "_l10n_ar_get_afip_ws_currency_rate", autospec=True, side_effect=fake_rate
            ),
        ):
            res = companies.with_context(**(context or {}))._parse_arca_data(currencies)
        return res, calls

    def _today_rates(self):
        return {"ARS": (1.0, self.today_str)} | {c.name: (0.001, self.today_str) for c in self.arca_currencies}

    def test_connect_with_rate_company(self):
        """With several Argentinian companies ARCA is asked with the company that has the certificate, even
        when the current company is another one"""
        self.assertNotEqual(self.env.company, self.company_2)
        _res, calls = self._parse(
            self.company_1 | self.company_2,
            {"USD": (0.001, self.today_str), "EUR": (0.0009, self.today_str)},
            rate_company=self.company_2,
        )
        self.assertEqual({name for _company, name in calls}, {"USD", "EUR"})
        for company, _name in calls:
            self.assertEqual(company, self.company_2)

    def test_error_in_one_currency_keeps_the_others(self):
        """An ARCA error in one currency does not stop the update of the other ones, as in 19.0"""
        res, calls = self._parse(
            self.company_1, {"USD": (0.001, self.today_str), "EUR": UserError("ARCA error for EUR")}
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(res["USD"], (0.001, self.today_str))
        self.assertNotIn("EUR", res)

    def test_skip_currencies_without_arca_code(self):
        """Currencies without ARCA code are not sent to ARCA, so the native error does not stop the update"""
        self.EUR.l10n_ar_afip_code = False
        _res, calls = self._parse(self.company_1, {"USD": (0.001, self.today_str)})
        sent = {name for _company, name in calls}
        self.assertIn("USD", sent)
        self.assertNotIn("EUR", sent)

    def test_no_foreign_currency_does_not_connect(self):
        """Without foreign currencies ARCA is not asked, and only the ARS rate is returned"""
        res, calls = self._parse(self.company_1, {}, currencies=self.ARS)
        self.assertFalse(calls)
        self.assertEqual(res, {"ARS": (1.0, self.today_str)})

    def test_only_today_rate(self):
        """A rate that is not today's is not kept"""
        res, _calls = self._parse(self.company_1, {"USD": (0.001, self.today_str), "EUR": (0.0009, self.yesterday_str)})
        self.assertEqual(res["USD"], (0.001, self.today_str))
        self.assertNotIn("EUR", res)
        self.assertEqual(res["ARS"], (1.0, self.today_str))

    def test_force_create_rate(self):
        """With l10n_ar_force_create_rate the last published rate is kept, dated today"""
        res, _calls = self._parse(
            self.company_1,
            {"USD": (0.001, self.yesterday_str)},
            context={"l10n_ar_force_create_rate": True},
        )
        self.assertEqual(res["USD"], (0.001, self.today_str))

    def test_no_company_with_valid_certificate(self):
        """Without a company with a valid certificate only ARS is returned, and the update does not fail"""
        res, calls = self._parse(self.company_1, {}, rate_company=self.env["res.company"])
        self.assertEqual(res, {"ARS": (1.0, self.today_str)})
        self.assertFalse(calls)
        with patch.object(
            type(self.env["res.company"]), "_l10n_ar_get_arca_rate_company", return_value=self.env["res.company"]
        ):
            self.assertTrue(self.company_1.update_currency_rates())
        self.assertFalse(self.company_1.l10n_ar_last_currency_sync_date)

    def test_connection_error(self):
        """A connection error stops asking ARCA, so no currency is asked, and only ARS is returned"""
        with self.assertLogs("odoo.addons.l10n_ar_currency_update.models.res_company", level="WARNING"):
            res, calls = self._parse(
                self.company_1, {"USD": (0.001, self.today_str)}, connection_error=UserError("WSAA error")
            )
        self.assertEqual(res, {"ARS": (1.0, self.today_str)})
        self.assertFalse(calls)

    def test_one_connection_for_all_currencies(self):
        """All the currencies are asked with one connection"""
        with patch.object(L10nArEdiResCompany, "_l10n_ar_get_connection", autospec=True) as get_connection:
            get_connection.return_value._get_client.return_value = ("client", "auth")
            with (
                patch.object(
                    type(self.env["res.company"]), "_l10n_ar_get_arca_rate_company", return_value=self.company_1
                ),
                patch.object(
                    L10nArEdiResCurrency,
                    "_l10n_ar_get_afip_ws_currency_rate",
                    autospec=True,
                    return_value=(None, False),
                ),
            ):
                self.company_1._parse_arca_data(self.ARS | self.USD | self.EUR)
        self.assertEqual(get_connection.call_count, 1)

    def test_sync_date_after_creating_rates(self):
        """The sync date is marked once the rates are created, and only if every currency has today's rate"""
        companies = self.company_1 | self.company_2
        with (
            patch.object(
                CurrencyRateLiveResCompany,
                "_generate_currency_rates",
                autospec=True,
                side_effect=UserError("rates failed"),
            ),
            self.assertRaises(UserError),
        ):
            companies._generate_currency_rates(self._today_rates())
        self.assertFalse(self.company_1.l10n_ar_last_currency_sync_date)

        missing = self._today_rates()
        missing.pop("USD")
        companies._generate_currency_rates(missing)
        self.assertFalse(self.company_1.l10n_ar_last_currency_sync_date)

        companies._generate_currency_rates(self._today_rates())
        self.assertEqual(self.company_1.l10n_ar_last_currency_sync_date, self.today)
        self.assertEqual(self.company_2.l10n_ar_last_currency_sync_date, self.today)

    def test_sync_date_with_loaded_rate(self):
        """A currency that ARCA did not return but is already loaded for the day counts as synced"""
        self.env["res.currency.rate"].create(
            {"currency_id": self.USD.id, "name": self.today, "rate": 0.002, "company_id": self.company_1.id}
        )
        missing = self._today_rates()
        missing.pop("USD")
        (self.company_1 | self.company_2)._generate_currency_rates(missing)
        self.assertEqual(self.company_1.l10n_ar_last_currency_sync_date, self.today)
        self.assertFalse(self.company_2.l10n_ar_last_currency_sync_date)

    def test_sync_date_without_foreign_currency(self):
        """Without foreign currencies the day is not marked, so the retry cron takes a currency added later"""
        self.arca_currencies.l10n_ar_afip_code = False
        (self.company_1 | self.company_2)._generate_currency_rates({"ARS": (1.0, self.today_str)})
        self.assertFalse(self.company_1.l10n_ar_last_currency_sync_date)

    def test_rate_company_certificate(self):
        """ARCA is asked with a company whose own certificate is valid, production first, then the current one"""
        certificate = (
            self.env["res.company"]
            .search([("l10n_ar_afip_ws_crt_id", "!=", False), ("l10n_ar_afip_ws_key_id", "!=", False)])
            .l10n_ar_afip_ws_crt_id.filtered("is_valid")[:1]
        )
        if not certificate:
            self.skipTest("Needs a valid ARCA certificate, as in the l10n_ar_edi demo data")
        for company in self.company_1 | self.company_2:
            key = certificate.private_key_id.copy({"company_id": company.id})
            company.write(
                {
                    "l10n_ar_afip_ws_crt_id": certificate.copy({"company_id": company.id, "private_key_id": key.id}).id,
                    "l10n_ar_afip_ws_key_id": key.id,
                }
            )
        others = self.env["res.company"].search([("l10n_ar_afip_ws_crt_id", "!=", False)]) - (
            self.company_1 | self.company_2
        )
        others.l10n_ar_afip_ws_environment = "testing"
        Company = self.env["res.company"].with_company(self.company_1)

        self.company_1.l10n_ar_afip_ws_environment = "testing"
        self.company_2.l10n_ar_afip_ws_environment = "production"
        self.assertEqual(Company._l10n_ar_get_arca_rate_company(), self.company_2)

        self.company_2.l10n_ar_afip_ws_environment = "testing"
        self.assertEqual(Company._l10n_ar_get_arca_rate_company(), self.company_1)

        # A certificate of another company is not used: ARCA authenticates with the CUIT of the company
        # The ORM does not allow it, but a certificate shared between companies can come from older data
        certificate_1 = self.company_1.l10n_ar_afip_ws_crt_id
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE certificate_certificate SET company_id = %s WHERE id = %s", (self.company_2.id, certificate_1.id)
        )
        certificate_1.invalidate_recordset(["company_id"])
        (self.company_1 | self.company_2).l10n_ar_afip_ws_environment = "production"
        self.assertEqual(Company._l10n_ar_get_arca_rate_company(), self.company_2)

        (others | self.company_1 | self.company_2).l10n_ar_afip_ws_crt_id.active = False
        self.assertFalse(Company._l10n_ar_get_arca_rate_company())

    def test_set_arca_provider_on_install(self):
        """On install the Argentinian companies that already exist get the ARCA provider"""
        branch = self.env["res.company"].create(
            {"name": "AR Branch", "parent_id": self.company_1.id, "country_id": self.env.ref("base.ar").id}
        )
        self.assertEqual(branch.country_id.code, "AR")
        (self.company_1 | branch).currency_provider = "ecb"
        self.env["res.company"]._l10n_ar_set_arca_currency_provider()
        self.assertEqual(self.company_1.currency_provider, "arca")
        self.assertEqual(branch.currency_provider, "ecb", "Rates are only created for main companies")

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

    def test_recheck_cron_weekly_and_monthly_on_their_day(self):
        """Weekly and monthly companies are retried on their day, with the last published rate, so their
        day does not move when today's rate is not published yet"""
        self.company_1.write(
            {"currency_interval_unit": "weekly", "l10n_ar_last_currency_sync_date": self.today - timedelta(days=7)}
        )
        self.company_2.write(
            {
                "currency_interval_unit": "monthly",
                "l10n_ar_last_currency_sync_date": self.today - relativedelta(months=1),
            }
        )
        weekly_not_due = self.env["res.company"].create(
            {"name": "AR Company 3", "country_id": self.env.ref("base.ar").id, "currency_id": self.ARS.id}
        )
        weekly_not_due.write(
            {
                "currency_provider": "arca",
                "currency_interval_unit": "weekly",
                "l10n_ar_last_currency_sync_date": self.today - timedelta(days=6),
            }
        )
        updated = self.env["res.company"]
        forced = self.env["res.company"]

        def fake_update(companies):
            nonlocal updated, forced
            updated |= companies
            if companies.env.context.get("l10n_ar_force_create_rate"):
                forced |= companies
            return True

        with patch.object(
            type(self.env["res.company"]), "update_currency_rates", autospec=True, side_effect=fake_update
        ):
            self.env["res.company"].re_check_arca_currency_rate()
        self.assertIn(self.company_1, forced)
        self.assertIn(self.company_2, forced)
        self.assertNotIn(weekly_not_due, updated)

    def test_recheck_cron_skips_branches(self):
        """Rates are only created for main companies, so the retry cron does not take branches"""
        branch = self.env["res.company"].create({"name": "AR Branch", "parent_id": self.company_1.id})
        branch.write({"currency_provider": "arca", "currency_interval_unit": "daily"})
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
        self.assertNotIn(branch, updated)
