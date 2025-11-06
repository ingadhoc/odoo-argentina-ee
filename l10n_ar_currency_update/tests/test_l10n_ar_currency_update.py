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
        print("Ejecutando test_ARS")
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

    def test_update_currency_rate_with_percentage_markup(self):
        """Test currency rate update with percentage markup for Argentina localization"""
        # Test values and data
        BASE_AFIP_RATE = 1109.649
        PERCENTAGE_MARKUP = 0.03
        TODAY = datetime.date.today()

        # Company configuration
        self.env.company.write(
            {
                "currency_provider": "afip",
                "rate_perc": PERCENTAGE_MARKUP,
                "currency_interval_unit": "daily",
            }
        )

        # Activate USD for the test
        self.USD.active = True

        # Clean up previous rates
        existing_rates = self.env["res.currency.rate"].search([("currency_id", "=", self.USD.id), ("name", "=", TODAY)])
        existing_rates.unlink()

        # Prepare mock data for AFIP
        mocked_res = {
            "USD": (1.0 / BASE_AFIP_RATE, TODAY),
        }

        # Execute test logic with patch
        with patch(f"{self.utils_path}._parse_afip_data", return_value=mocked_res):
            self.env.company.update_currency_rates()

        # Validate rate creation
        rate_record = self.env["res.currency.rate"].search([("currency_id", "=", self.USD.id), ("name", "=", TODAY)])

        self.assertTrue(rate_record, "No currency rate record was created for USD today.")
        self.assertEqual(len(rate_record), 1, "More than one rate record was created for the same date.")

        # Validate calculated data
        # In Odoo, the 'rate' field is the inverse of the real rate (1 / real rate)
        # The logic applies: rate = 1/((1/base_rate) * (1 + markup))
        # Simplified: rate = base_rate / (1 + markup)
        expected_rate_with_markup = BASE_AFIP_RATE * (1 + PERCENTAGE_MARKUP)
        expected_odoo_rate = 1 / expected_rate_with_markup

        self.assertAlmostEqual(
            rate_record.rate,
            expected_odoo_rate,
            places=8,
            msg="The 'rate' field value does not match the expected value with markup.",
        )

        # Verify markup was applied correctly
        # The inverse rate (ARS per USD unit) should be BASE_AFIP_RATE * (1 + PERCENTAGE_MARKUP)
        inverse_rate = 1 / rate_record.rate
        expected_inverse_rate = BASE_AFIP_RATE * (1 + PERCENTAGE_MARKUP)

        self.assertAlmostEqual(
            inverse_rate,
            expected_inverse_rate,
            places=2,
            msg="The inverse rate value (ARS per unit) with markup is incorrect.",
        )
