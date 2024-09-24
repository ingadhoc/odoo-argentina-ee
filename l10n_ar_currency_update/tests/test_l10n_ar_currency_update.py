##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import datetime
from unittest import mock
from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TestL10nArCurrencyUpdate(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref="ar_ri"):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.ARS = cls.env.ref('base.ARS')
        cls.USD = cls.env.ref('base.USD')
        cls.EUR = cls.env.ref('base.EUR')

        # Activamos monedas por las dudas
        cls.USD.active = True
        cls.EUR.active = True
        cls.utils_path = "odoo.addons.l10n_ar_currency_update.models.res_company.ResCompany"

    def test_ARS(self):
        """ When the base currency is ARS """
        msg_error = "Should not be any rate for this currency and company to continue with the test"
        self.assertEqual(self.env.company.currency_id, self.ARS)
        self.assertEqual(self.ARS.rate, 1.0, msg_error)
        self.assertEqual(self.USD.rate, 1.0, msg_error)
        self.assertEqual(self.EUR.rate, 1.0, msg_error)

        test_date = datetime.date(2024, 9, 24)
        mocked_res = {
            'ARS': (1.0, test_date),
            'EUR': (0.0009435361546070796, test_date),
            'USD': (0.0010481301358376655, test_date),
        }

        with patch(f"{self.utils_path}._parse_afip_data", return_value=mocked_res):
            self.env.company.update_currency_rates()

        self.assertEqual(self.ARS.rate, 1.0)
        self.assertNotEqual(self.USD.rate, 954.08)
        self.assertNotEqual(self.EUR.rate, 1059.8428)
