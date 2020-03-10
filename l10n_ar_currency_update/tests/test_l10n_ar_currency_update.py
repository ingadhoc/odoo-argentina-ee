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

        self.ARS_USD = 62.073
        self.ARS_EUR = 60.073
        self.USD_EUR = 1.575

        super().setUp()

        self.ARS = self.env.ref('base.ARS')
        self.USD = self.env.ref('base.USD')
        self.EUR = self.env.ref('base.EUR')

    def test_ARS(self):
        """ When the base currency is ARS """
        company = self.env.ref('l10n_ar.company_ri')
        company.currency_id = self.ARS
        self.env.company = company

        company.update_currency_rates()
        pprint.pprint(self.env['res.currency'].search([]).read(['name', 'date', 'rate']))

        self.assertEqual(self.ARS.rate, 1.0)
        self.assertAlmostEqual(self.USD.rate, self.ARS_USD, places=3)
        self.assertAlmostEqual(self.EUR.rate, self.ARS_EUR, places=3)
