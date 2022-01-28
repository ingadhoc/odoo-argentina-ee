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
    l10n_ar_last_currency_sync_date = fields.Date(string="AFIP Last Sync Date", readonly=True)

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
            ('currency_interval_unit', '!=', 'manually'),
            '|', ('l10n_ar_last_currency_sync_date', '<', fields.Date.context_today(self.with_context(tz='America/Argentina/Buenos_Aires'))),
            ('l10n_ar_last_currency_sync_date', '=', False),
        ])
        records.update_currency_rates()

    def _parse_afip_data(self, available_currencies):
        """ This method is used to update the currency rates using AFIP provider. Rates are given against AR """
        res = {}

        currency_ars = self.env.ref('base.ARS')
        today = fields.Date.context_today(self.with_context(tz='America/Argentina/Buenos_Aires'))
        if currency_ars in available_currencies:
            res['ARS'] = (1.0, today)
        available_currencies = available_currencies.filtered('l10n_ar_afip_code') - currency_ars
        rate_date = today

        for currency in available_currencies:
            company = self.env.company if self.env.company.sudo().l10n_ar_afip_ws_crt else self.env['res.company'].search(
                [('l10n_ar_afip_ws_crt', '!=', False)], limit=1)
            if not company:
                _logger.log(25, "No pudimos encontrar compañía con certificados de AFIP validos")
                return False
            env_company = self.env.company
            self.env.company = company
            try:
                # Obtain the currencies to be updated
                _logger.log(25, "Connecting to AFIP to update the currency rates for %s", currency.name)

                # Do not pass company since we need to find the one that has certificate
                afip_date, rate = currency._l10n_ar_get_afip_ws_currency_rate()

                if datetime.strptime(afip_date, "%Y%m%d").date() + relativedelta(days=1) == rate_date:
                    res.update({currency.name: (1.0 / rate, rate_date)})
                    _logger.log(25, "Currency %s %s %s", currency.name, rate_date, rate)
                self.env.company = env_company
            except Exception as e:
                self.env.company = env_company
                _logger.log(25, "Could not get rate for currency %s. This is what we get:\n%s", currency.name, e)
        return res or False

    def _generate_currency_rates(self, parsed_data):
        """ Apply surcharge for on afip rates """
        currency_rate = self.env['res.currency.rate']
        currency_object = self.env['res.currency']
        for company in self:
            if company.currency_provider == 'afip':
                new_parsed_data = parsed_data.copy()

                # condicion 1: si ya existe la tasa para el dia de una moneda en especifco usamos dicha tasa pre
                # existente y no usamos las que nos dio AFIP
                for currency, (rate, date_rate) in new_parsed_data.items():
                    currency_object = currency_object.search([('name', '=', currency)])
                    already_existing_rate = currency_rate.search([
                        ('currency_id', '=', currency_object.id),
                        ('name', '=', date_rate),
                        ('company_id', '=', company.id)])
                    if already_existing_rate:
                        new_parsed_data[currency] = (already_existing_rate.rate, date_rate)
                    elif company.rate_surcharge or company.rate_perc:
                        # condicion 2: Si tenemos definido una tasa de recargo o una percepcion definido en la compañia
                        # necesitamos volver a calcula la información de la tasa AFIP mas esos montos extras
                        if rate and rate != 1.0:
                            rate = 1.0 / rate
                            rate = rate * (1.0 + (company.rate_perc or 0.0))
                            rate += (company.rate_surcharge or 0.0)
                            rate = 1.0 / rate
                        new_parsed_data[currency] = (rate, date_rate)

                super(ResCompany, company)._generate_currency_rates(new_parsed_data)
            else:
                super(ResCompany, company)._generate_currency_rates(parsed_data)
            if company.currency_provider == 'afip':
                company.l10n_ar_last_currency_sync_date = fields.Date.context_today(self.with_context(tz='America/Argentina/Buenos_Aires'))
