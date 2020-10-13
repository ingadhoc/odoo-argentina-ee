##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):

    _inherit = 'res.company'

    currency_provider = fields.Selection(
        selection_add=[('afip', 'AFIP Web Service (Argentina)')],
        default='afip',
    )
    rate_perc = fields.Float(
        digits=(16, 4),
    )
    rate_surcharge = fields.Float(
        digits=(16, 4),
    )

    @api.model
    def create(self, values):
        """ Overwrite to include new currency provider """
        if values.get('country_id') and 'currency_provider' not in values:
            country = self.env['res.country'].browse(values['country_id'])
            if country.code.upper() == 'AR':
                values['currency_provider'] = 'afip'
        return super().create(values)

    @api.model
    def set_special_defaults_on_install(self):
        """ Overwrite to include new currency provider """
        super().set_special_defaults_on_install()
        ar_companies = self.search([]).filtered(lambda company: company.country_id.code == 'AR')
        if ar_companies:
            ar_companies.currency_provider = 'afip'
            _logger.log(25, "Currency Provider configured as AFIP for next companies: %s", ', '.join(
                ar_companies.mapped('name')))

    @api.model
    def re_check_afip_currency_rate(self):
        """ If afip provider and set interval unit daily then check the
        currency multiple times at day (in case the default odoo cron couldn't
        update the currency with AFIP) """
        records = self.search([
            ('currency_provider', '=', 'afip'),
            ('currency_interval_unit', '!=', False),
            '|', ('currency_next_execution_date', '<', fields.Date.today()),
            ('currency_next_execution_date', '=', False),
        ])
        for rec in records:
            rec.update_currency_rates()

    def _parse_afip_data(self, available_currencies):
        """ This method is used to update the currency rates using AFIP provider. Rates are given against AR """
        res = {}

        currency_ars = self.env.ref('base.ARS')
        if currency_ars in available_currencies:
            res['ARS'] = (1.0, fields.Date.today())
        available_currencies = available_currencies.filtered('l10n_ar_afip_code') - currency_ars

        for currency in available_currencies:
            try:
                # Obtain the currencies to be updated
                _logger.log(25, "Connecting to AFIP to update the currency rates for %s", currency.name)

                # Do not pass company since we need to find the one that has certificate
                afip_date, rate = currency._l10n_ar_get_afip_ws_currency_rate()

                res.update({currency.name: (1.0 / rate, datetime.strptime(afip_date, "%Y%m%d").date())})

                _logger.log(25, "Currency %s %s %s", currency.name, afip_date, rate)
            except Exception:
                return False
        return res or False

    def _generate_currency_rates(self, parsed_data):
        """ Apply surcharge for on afip rates """
        for company in self:
            if company.currency_provider == 'afip' and (company.rate_surcharge or company.rate_perc):
                new_parsed_data = parsed_data.copy()
                for currency, (rate, date_rate) in new_parsed_data.items():
                    if rate and rate != 1.0:
                        rate = 1.0 / rate
                        rate = rate * (1.0 + (company.rate_perc or 0.0))
                        rate += (company.rate_surcharge or 0.0)
                        rate = 1.0 / rate
                    new_parsed_data[currency] = (rate, date_rate)
                super(ResCompany, company)._generate_currency_rates(new_parsed_data)
            else:
                super(ResCompany, company)._generate_currency_rates(parsed_data)
