##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import datetime
from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestL10nArCurrencyUpdate(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_chart_template("ar_ri")
    def setUpClass(cls):
        super().setUpClass()
        cls.ARS = cls.env.ref("base.ARS")
        cls.USD = cls.env.ref("base.USD")
        cls.EUR = cls.env.ref("base.EUR")

        # Activamos monedas por las dudas
        cls.USD.active = True
        cls.EUR.active = True
        cls.utils_path = "odoo.addons.l10n_ar_currency_update.models.res_company.ResCompany"

    def test_ARS(self):
        """When the base currency is ARS"""
        msg_error = "Should not be any rate for this currency and company to continue with the test"
        self.assertEqual(self.env.company.currency_id, self.ARS)
        self.assertEqual(self.ARS.rate, 1.0, msg_error)
        self.assertEqual(self.USD.rate, 1.0, msg_error)
        self.assertEqual(self.EUR.rate, 1.0, msg_error)

        test_date = datetime.date(2024, 9, 24)
        mocked_res = {
            "ARS": (1.0, test_date),
            "EUR": (0.0009435361546070796, test_date),
            "USD": (0.0010481301358376655, test_date),
        }

        with patch(f"{self.utils_path}._parse_afip_data", return_value=mocked_res):
            self.env.company.update_currency_rates()

        self.assertEqual(self.ARS.rate, 1.0)
        self.assertNotEqual(self.USD.rate, 954.08)
        self.assertNotEqual(self.EUR.rate, 1059.8428)

    def test_currency_rate_with_rate_perc(self):
        """Check that the rate percentage is applied only to company 1 when both sync from ARCA"""
        # Test values and data
        base_arca_rate = 1109.649
        rate_perc = 0.03
        test_date = datetime.date.today()

        # Create a second Argentine company
        ar_country = self.env.ref("base.ar")
        company_2 = self.env["res.company"].create(
            {
                "name": "Test Argentine Company 2",
                "country_id": ar_country.id,
                "currency_id": self.ARS.id,
                "tax_calculation_rounding_method": "round_globally",
            }
        )

        # Configure the first company (self.env.company) with currency provider AND rate_perc
        self.env.company.write(
            {
                "currency_provider": "afip",
                "rate_perc": rate_perc,
                "currency_interval_unit": "daily",
            }
        )

        # Configure the second company with currency provider but WITHOUT rate_perc
        company_2.write(
            {
                "currency_provider": "afip",
                "currency_interval_unit": "daily",
            }
        )

        # Clean up previous rates for both companies
        existing_rates = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.USD.id),
                ("name", "=", test_date),
                ("company_id", "in", [self.env.company.id, company_2.id]),
            ]
        )
        existing_rates.unlink()

        # Prepare mock data for AFIP
        mocked_res = {
            "ARS": (1.0, test_date),
            "USD": (1.0 / base_arca_rate, test_date),
        }

        # Execute test logic with patch - call update_currency_rates on both companies
        with patch(f"{self.utils_path}._parse_afip_data", return_value=mocked_res):
            (self.env.company | company_2).update_currency_rates()

        # Validate rate creation for company 1 (WITH percentage rate_perc)
        rate_record_company_1 = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.USD.id),
                ("name", "=", test_date),
                ("company_id", "=", self.env.company.id),
            ]
        )

        self.assertTrue(rate_record_company_1, "No currency rate record was created for USD today in company 1.")
        self.assertEqual(
            len(rate_record_company_1), 1, "More than one rate record was created for the same date in company 1."
        )

        # Verify markup was applied correctly for company 1
        # The inverse rate (ARS per USD unit) should be base_arca_rate * (1 + rate_perc)
        inverse_rate_company_1 = 1 / rate_record_company_1.rate
        expected_inverse_rate_company_1 = base_arca_rate * (1 + rate_perc)

        self.assertAlmostEqual(
            inverse_rate_company_1,
            expected_inverse_rate_company_1,
            places=2,
            msg="The inverse rate value (ARS per unit) with markup is incorrect for company 1.",
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
        inverse_rate_company_2 = 1 / rate_record_company_2.rate

        self.assertAlmostEqual(
            inverse_rate_company_2,
            base_arca_rate,
            places=2,
            msg="The inverse rate value (ARS per unit) should be the base ARCA rate for company 2 (no markup).",
        )

        # Verify that the rates are different between companies
        self.assertNotEqual(
            rate_record_company_1.rate,
            rate_record_company_2.rate,
            "Company 1 and Company 2 should have different rates due to the markup applied only to Company 1.",
        )
