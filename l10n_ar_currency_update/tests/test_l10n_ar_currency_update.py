##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.tests import common
from odoo import fields
import pprint


class TestL10nArCurrencyUpdate(common.TransactionCase):

    # TODO when runing this test please update this values to the day rate

    def setUp(self):

        self.ARS_USD = 38.126
        self.ARS_EUR = 60.126
        self.USD_EUR = 1.5770

        super(TestL10nArCurrencyUpdate, self).setUp()
        rates = self.env['res.currency.rate'].search([
            ('name', '=', fields.Date.today())])
        if rates:
            rates.unlink()
        self.company = self.env.ref('base.main_company')

        self.ARS = self.env.ref('base.ARS')
        self.USD = self.env.ref('base.USD')
        self.EUR = self.env.ref('base.EUR')

    def _update_base_currency(self, currency):
        self.env['res.currency.rate'].create({
            'name': fields.Date.today(),
            'rate': 1.0,
            'currency_id': currency.id,
            'company_id': self.company.id,
        })

    def test_ARS(self):
        """ When the base currency is ARS
        """
        self._update_base_currency(self.ARS)
        self.company._update_currency_afip()
        pprint.pprint(self.env['res.currency'].search([]).read([
            'name', 'date', 'rate', 'inverse_rate']))

        self.assertEqual(self.ARS.rate, 1.0)

        self.assertAlmostEqual(self.USD.rate, 1.0 / self.ARS_USD, 3)
        self.assertAlmostEqual(self.USD.inverse_rate, self.ARS_USD)

        self.assertAlmostEqual(self.EUR.rate, 1.0 / self.ARS_EUR, 3)
        self.assertAlmostEqual(self.EUR.inverse_rate, self.ARS_EUR)

    def test_USD(self):
        """ When the base currency is USD
        """
        self._update_base_currency(self.USD)
        self.company._update_currency_afip()
        pprint.pprint(self.env['res.currency'].search([]).read([
            'name', 'date', 'rate', 'inverse_rate']))

        self.assertEqual(self.USD.rate, 1.0)

        self.assertAlmostEqual(self.ARS.rate, self.ARS_USD)
        self.assertAlmostEqual(self.ARS.inverse_rate, 1.0 / self.ARS_USD, 3)

        self.assertAlmostEqual(
            self.EUR.rate, 1.0 / self.USD_EUR, 3, msg='EUR RATE')
        self.assertAlmostEqual(
            self.EUR.inverse_rate, self.USD_EUR, 3, msg='EUR INV RATE')

    def test_EUR(self):
        """ When the base currency is EUR
        """
        self._update_base_currency(self.EUR)
        self.company._update_currency_afip()
        pprint.pprint(self.env['res.currency'].search([]).read([
            'name', 'date', 'rate', 'inverse_rate']))

        self.assertEqual(self.EUR.rate, 1.0)

        self.assertAlmostEqual(self.ARS.rate, self.ARS_EUR, msg='ARS RATE')
        self.assertAlmostEqual(
            self.ARS.inverse_rate, 1.0 / self.ARS_EUR, 3, msg='ARS INV RATE')

        self.assertAlmostEqual(self.USD.rate, self.USD_EUR, 3, msg='USD RATE')
        self.assertAlmostEqual(
            self.USD.inverse_rate, 1.0 / self.USD_EUR, 3, msg='USD INV RATE')
