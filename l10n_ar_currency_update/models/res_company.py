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
        ar_companies = self.search([]).filtered(
            lambda company: company.country_id.code == 'AR')
        if ar_companies:
            ar_companies.write({
                'currency_provider': 'afip',
            })
            _logger.log(
                25, "Currency Provider configured as AFIP for next"
                " companies: %s", ', '.join(ar_companies.mapped('name')))

    @api.multi
    def update_currency_rates(self):
        """ Overwrite to include new currency provider """
        all_good = True
        afip_companies = self.filtered(lambda x: x.currency_provider == 'afip')
        for company in afip_companies:
            _logger.log(25, "Connecting to AFIP to update the currency rates"
                        " for %s", company.name)
            res = company._update_currency_afip()
            if not res:
                all_good = False
                _logger.warning(_(
                    'Unable to connect to the online exchange rate platform'
                    ' %s. The web service may be temporary down.') %
                    company.currency_provider)
            elif company.currency_provider:
                company.last_currency_sync_date = fields.Date.today()
        res = super(ResCompany, self - afip_companies).update_currency_rates()
        return all_good and res

    @api.model
    def re_check_afip_currency_rate(self):
        """ If afip provider and set interval unit daily then check the
        currency multiple times at day (in case the default odoo cron couldn't
        update the currency with AFIP)
        """
        records = self.search([
            ('currency_interval_unit', '=', 'daily'),
            ('currency_provider', '=', 'afip'),
            '|', ('last_currency_sync_date', '<', fields.Date.today()),
            ('last_currency_sync_date', '=', False),
        ])
        records.update_currency_rates()

    @api.multi
    def _update_currency_afip(self):
        """ This method is used to update the currency rates using AFIP
        provider. Rates are given against AR.
        """
        self.ensure_one()
        _logger.log(
            25,
            'Starting to refresh currencies with provider %s (company: %s)',
            self.currency_provider, self.name)
        rate_obj = self.env['res.currency.rate']

        # Obtain the currencies to be updated
        factor = 1.0
        currency_ars = self.env.ref('base.ARS')
        currency_to_update = self.env['res.currency'].search([
            ('afip_code', '!=', False)]) - currency_ars
        rate_date = fields.Date.today()
        if currency_ars.with_context(company_id=self.id).rate != 1.0:

            # we get one base currency to get ARS rates
            base_currency = self.env['res.currency.rate'].search([
                ('rate', '=', 1.0), '|', ('company_id', '=', self.id),
                ('company_id', '=', False)],
                limit=1, order='company_id, name desc').currency_id
            base_currency = base_currency or self.currency_id

            _logger.log(25, "Compute ARS from Base Currency %s",
                        base_currency.name)

            rate = False
            msg = ''
            try:
                # Do not pass company since we need to find the one that has
                # certificate
                rate, msg, afip_date = \
                    base_currency.get_pyafipws_currency_rate()
            except Exception as exc:
                _logger.error(repr(exc) + '\n' + msg)
            if not rate or datetime.strptime(afip_date, "%Y%m%d").date() + \
               relativedelta(days=1) != fields.Date.from_string(rate_date):
                _logger.error(
                    'Could not update currency %s via provider %s. %s',
                    currency_ars.name, self.currency_provider, msg)
                return False
            rate = rate * (1.0 + (self.rate_perc or 0.0))
            rate += self.rate_surcharge or 0.0
            values = {
                'currency_id': currency_ars.id,
                'rate': rate,
                'name': rate_date,
                'company_id': self.id
            }
            factor = 1.0 / rate
            rate_obj.create(values)
            currency_to_update -= base_currency

        all_good = True
        for currency in currency_to_update:
            rate = False
            msg = ''
            try:
                # Do not pass company since we need to find the one that has
                # certificate
                rate, msg, afip_date = currency.get_pyafipws_currency_rate()
            except Exception as exc:
                _logger.error(repr(exc))
            if not rate or datetime.strptime(afip_date, "%Y%m%d").date() + \
               relativedelta(days=1) != fields.Date.from_string(rate_date):
                all_good = False
                _logger.error(
                    'Could not update currency %s via provider %s. %s',
                    currency.name, self.currency_provider, msg)
                continue
            rate = (rate * factor) * (1.0 + (self.rate_perc or 0.0))
            rate += self.rate_surcharge or 0.0
            rate = 1.0 / rate
            values = {
                'currency_id': currency.id,
                'rate': rate,
                'name': rate_date,
                'company_id': self.id
            }
            rate_obj.create(values)
            _logger.info(
                'Updated currency %s via provider %s',
                currency.name, self.currency_provider)
        return all_good
