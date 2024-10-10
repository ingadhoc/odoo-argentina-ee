##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):

    _inherit = 'res.company'

    currency_provider = fields.Selection(
        selection_add=[('afip', 'AFIP Web Service (Argentina)')],
    )
    rate_perc = fields.Float(
        digits=(16, 4),
    )
    rate_surcharge = fields.Float(
        digits=(16, 4),
    )
    l10n_ar_last_currency_sync_date = fields.Date(string="AFIP Last Sync Date", readonly=True)

    @api.model
    def _compute_currency_provider(self):
        """ Overwrite to include new currency provider """
        super()._compute_currency_provider()
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
            res[currency_ars.name] = (1.0, today)
        available_currencies = available_currencies.filtered('l10n_ar_afip_code') - currency_ars
        rate_date = today

        for currency in available_currencies:
            valid_certificate = self.env['certificate.certificate'].search(
                [('active', '=', True), ('date_end', '>=', today), ("country_code", "=", "AR")])
            if self.env.company.l10n_ar_afip_ws_crt_id in valid_certificate:
                company = self.env.company
            else:
                company = valid_certificate[:1].company_id if valid_certificate else False
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
            else:
                for company in self.filtered(lambda x: x.currency_provider == 'afip'):
                    company.l10n_ar_last_currency_sync_date = fields.Date.context_today(self.with_context(tz='America/Argentina/Buenos_Aires'))
        return res or False

    def _generate_currency_rates(self, parsed_data):
        """ Apply surcharge for on afip rates
             Si tenemos definido una tasa de recargo o una percepcion definido en la compañia AR
             necesitamos volver a calcular la información de la tasa AFIP mas esos montos extras
        """
        currency_rate = self.env['res.currency.rate']
        currency_object = self.env['res.currency']
        for company in self.filtered(lambda x: x.currency_provider == 'afip' and (x.rate_surcharge or x.rate_perc)):
            for currency, (rate, date_rate) in parsed_data.items():
                already_existing_rate = currency_rate.search([
                    ('currency_id', '=', currency_object.search([('name', '=', currency)]).id),
                    ('name', '=', date_rate),
                    ('company_id', '=', company.id)])
                if not already_existing_rate and rate and rate != 1.0:
                    rate = 1.0 / rate
                    rate = rate * (1.0 + (company.rate_perc or 0.0))
                    rate += (company.rate_surcharge or 0.0)
                    rate = 1.0 / rate
                    parsed_data[currency] = (rate, date_rate)

        super()._generate_currency_rates(parsed_data)
