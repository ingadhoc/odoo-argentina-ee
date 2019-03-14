##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
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
        return super(ResCompany, self).create(values)

    @api.model
    def set_special_defaults_on_install(self):
        """ Overwrite to include new currency provider """
        super(ResCompany, self).set_special_defaults_on_install()
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
        res = super(ResCompany, self).update_currency_rates()
        afip_companies = self.filtered(lambda x: x.currency_provider == 'afip')
        for company in afip_companies:
            _logger.log(25, "Connecting to AFIP to update the currency rates"
                        " for %s", company.name)
            res = company._update_currency_afip()
            if not res:
                _logger.warning(_(
                    'Unable to connect to the online exchange rate platform'
                    ' %s. The web service may be temporary down.') %
                    company.currency_provider)
                continue
            company.last_currency_sync_date = fields.Date.today()
        return res

    @api.multi
    def _update_currency_afip(self):
        """ This method is used to update the currency rates using AFIP provider
        provider. Rates are given against AR.
        """
        self.ensure_one()
        _logger.log(
            25,
            'Starting to refresh currencies with provider %s (company: %s)',
            self.currency_provider, self.name)
        rate_obj = self.env['res.currency.rate']

        # Check proper main currency configuration
        main_currency = self.currency_id
        if not main_currency:
            raise UserError(_('There is no main currency defined!'))
        if main_currency.name != 'ARS':
            raise UserError(_('For AFIP WS base currency must be ARS!'))
        if main_currency.rate != 1:
            raise UserError(_('Base currency rate should be 1.00!'))

        # Obtain the currencies to be updated
        afip_supported_currency = [
            'USD', 'EUR', 'AUD', 'CAD', 'GBP', 'JPY', 'MXN', 'UYU', 'VEF']
        available_currencies = self.env['res.currency'].search([])
        currency_to_update = list(
            set(available_currencies.mapped('name')).intersection(
                set(afip_supported_currency))
        )
        currency_to_update = self.env['res.currency'].search(
            [('name', 'in', currency_to_update)])
        rate_name = fields.Date.today()
        for currency in currency_to_update:
            rate = False
            msg = ''
            try:
                # Do not pass company since we need to find the one that has
                # certificate
                rate, msg = currency.get_pyafipws_currency_rate()
            except Exception as exc:
                _logger.error(repr(exc))
            if rate:
                # impr when ARS is not base currency (rate 1.0)
                # company_rate = rate / base_currency_rate
                rate = rate * (1.0 + (self.rate_perc or 0.0))
                rate += self.rate_surcharge or 0.0
                rate = 1.0 / rate
                rate_obj.create({
                    'currency_id': currency.id,
                    'rate': rate,
                    'name': rate_name,
                    'company_id': self.id
                })
                _logger.info(
                    'Updated currency %s via provider %s',
                    currency.name, self.currency_provider)
            else:
                _logger.error(
                    'Could not update currency %s via provider %s. %s',
                    currency.name, self.currency_provider, msg)
                raise UserError(_(
                    'Could not update currency %s via provider %s. %s') %
                    (currency.name, self.currency_provider, msg)
                )
        return True
