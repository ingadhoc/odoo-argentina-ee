##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.tests import common, tagged


@tagged('-at_install', '-standard', 'currency_update')
class TestL10nArCurrencyUpdate(common.TransactionCase):

    # TODO when runing this test please update this values to the day rate

    def setUp(self):

        self.ARS_USD = 1 / 128.178
        self.ARS_EUR = 1 / 60.178
        # sin uso por ahora
        # self.USD_EUR = self.ARS_USD / self.ARS_EUR

        super().setUp()

        self.ARS = self.env.ref('base.ARS')
        self.USD = self.env.ref('base.USD')
        self.EUR = self.env.ref('base.EUR')

        # activamos monedas por las dudas
        self.USD.active = True
        self.EUR.active = True

    def test_ARS(self):
        """ When the base currency is ARS """
        company = self.env.ref('l10n_ar.company_ri')
        company.currency_id = self.ARS
        self.env.company = company

        company.update_currency_rates()

        self.assertEqual(self.ARS.rate, 1.0)
        self.assertAlmostEqual(self.USD.rate, self.ARS_USD, places=3)
        self.assertAlmostEqual(self.EUR.rate, self.ARS_EUR, places=3)
