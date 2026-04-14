##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import datetime
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestL10nArCurrencyUpdate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ARS = cls.env.ref("base.ARS")
        cls.USD = cls.env.ref("base.USD")
        cls.EUR = cls.env.ref("base.EUR")

        # Activamos monedas
        cls.USD.active = True
        cls.EUR.active = True
        cls.utils_path = "odoo.addons.l10n_ar_currency_update.models.res_company.ResCompany"

    def test_ARS(self):
        """Cuando se hace la actualización de monedas desde ARCA, siempre tenemos que validar que se actualice la moneda local (ARS) aunque su tipo de cambio sea 1.0 .
        Esto es requerido por validaciones de contabilidad en método _generate_currency_rates de src/enterprise/currency_rate_live/models/res_config_settings.py.
        Si no actualizamos la moneda local, no se crea ningún registro de tipo de cambio para esa fecha y empresa."""
        test_date = datetime.date(2026, 9, 24)

        # Clean existing rates for test isolation
        self.env["res.currency.rate"].search(
            [
                ("name", "=", test_date),
                ("company_id", "=", self.env.company.id),
            ]
        ).unlink()

        # Configure company to use AFIP provider
        self.env.company.write(
            {
                "currency_provider": "afip",
                "currency_interval_unit": "daily",
            }
        )

        # Mock data must include base currency for enterprise validation
        mocked_res = {
            "ARS": (1.0, test_date),
            "EUR": (0.0009435361546070796, test_date),
            "USD": (0.0010481301358376655, test_date),
        }

        with patch(f"{self.utils_path}._parse_afip_data", return_value=mocked_res):
            self.env.company.with_context(l10n_ar_force_create_rate=True).update_currency_rates()

        # Base currency WILL have a rate created with rate=1.0 (expected behavior)
        base_rate = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.env.company.currency_id.id),
                ("name", "=", test_date),
                ("company_id", "=", self.env.company.id),
            ]
        )
        self.assertTrue(base_rate, "Base currency should have a rate created")
        self.assertEqual(base_rate.rate, 1.0, "Base currency rate should be 1.0")

        # Verify other currencies got rates created
        for curr_code in mocked_res.keys():
            if curr_code != self.env.company.currency_id.name:
                if curr := self.env["res.currency"].search([("name", "=", curr_code)]):
                    rate = self.env["res.currency.rate"].search(
                        [
                            ("currency_id", "=", curr.id),
                            ("name", "=", test_date),
                            ("company_id", "=", self.env.company.id),
                        ]
                    )
                    self.assertTrue(rate, f"{curr_code} should have a rate created")

    def test_currency_rate_with_rate_perc(self):
        """Check that the rate percentage is applied only to company 1 when both sync from ARCA"""
        # Test values and data
        base_arca_rate = 1109.649
        rate_perc = 0.03
        test_date = datetime.date.today()

        # Create two fresh Argentine companies to avoid currency change issues
        ar_country = self.env.ref("base.ar")
        company_1 = self.env["res.company"].create(
            {
                "name": "Test Argentine Company 1",
                "country_id": ar_country.id,
                "currency_id": self.ARS.id,
            }
        )
        company_2 = self.env["res.company"].create(
            {
                "name": "Test Argentine Company 2",
                "country_id": ar_country.id,
                "currency_id": self.ARS.id,
            }
        )

        # Configure company_1 with currency provider AND rate_perc
        company_1.write(
            {
                "currency_provider": "afip",
                "rate_perc": rate_perc,
                "currency_interval_unit": "daily",
            }
        )

        # Configure company_2 with currency provider but WITHOUT rate_perc
        company_2.write(
            {
                "currency_provider": "afip",
                "currency_interval_unit": "daily",
                "rate_perc": 0.0,  # Explicitly no markup
            }
        )

        # Clean up previous rates for both companies
        self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.USD.id),
                ("name", "=", test_date),
                ("company_id", "in", [company_1.id, company_2.id]),
            ]
        ).unlink()

        # Prepare mock data for AFIP
        mocked_res = {
            "ARS": (1.0, test_date),  # Base currency for both companies
            "USD": (1.0 / base_arca_rate, test_date),
        }

        # Execute test logic with patch - call update_currency_rates on both companies
        with patch(f"{self.utils_path}._parse_afip_data", return_value=mocked_res):
            (company_1 | company_2).with_context(l10n_ar_force_create_rate=True).update_currency_rates()

        # Validate rate creation for company 1 (WITH percentage rate_perc)
        rate_record_company_1 = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.USD.id),
                ("name", "=", test_date),
                ("company_id", "=", company_1.id),
            ]
        )

        self.assertTrue(rate_record_company_1, "No currency rate record was created for USD today in company 1.")
        self.assertEqual(
            len(rate_record_company_1), 1, "More than one rate record was created for the same date in company 1."
        )

        # Verify markup was applied correctly for company 1
        # In Odoo, rate field = 1 / (ARS per USD)
        # With markup: ARS_per_USD = base_arca_rate * (1 + rate_perc)
        # So rate field = 1 / (base_arca_rate * (1 + rate_perc))
        expected_rate_with_markup = 1.0 / (base_arca_rate * (1 + rate_perc))

        self.assertAlmostEqual(
            rate_record_company_1.rate,
            expected_rate_with_markup,
            places=6,
            msg="The rate with markup is incorrect for company 1.",
        )

        # Validate rate creation for company 2 (WITHOUT rate_perc)
        rate_record_company_2 = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.USD.id),
                ("name", "=", test_date),
                ("company_id", "=", company_2.id),
            ]
        )

        self.assertTrue(rate_record_company_2, "No currency rate record was created for USD today in company 2.")
        self.assertEqual(
            len(rate_record_company_2), 1, "More than one rate record was created for the same date in company 2."
        )

        # Verify NO markup was applied for company 2 (base ARCA rate)
        expected_rate_no_markup = 1.0 / base_arca_rate

        self.assertAlmostEqual(
            rate_record_company_2.rate,
            expected_rate_no_markup,
            places=6,
            msg="The rate should be the base ARCA rate for company 2 (no markup).",
        )

        # Verify that the rates are different between companies
        self.assertNotEqual(
            rate_record_company_1.rate,
            rate_record_company_2.rate,
            "Company 1 and Company 2 should have different rates due to the markup applied only to Company 1.",
        )

    def test_protected_currency_name_cannot_be_changed(self):
        with self.assertRaisesRegex(UserError, "No se puede cambiar el nombre/código"):
            self.USD.write({"name": "USX"})

    def test_non_protected_currency_name_can_be_changed(self):
        custom_currency = self.env["res.currency"].create(
            {
                "name": "XCU",
                "symbol": "X$",
                "rounding": 0.01,
            }
        )
        custom_currency.write({"name": "XC2"})
        self.assertEqual(custom_currency.name, "XC2")
