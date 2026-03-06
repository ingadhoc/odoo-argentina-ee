##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("afip", "AFIP Web Service (Argentina)")],
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
        """Overwrite to include new currency provider"""
        super()._compute_currency_provider()
        ar_companies = self.search([]).filtered(lambda company: company.country_id.code == "AR")
        if ar_companies:
            ar_companies.currency_provider = "afip"
            _logger.log(
                25,
                "Currency Provider configured as AFIP for next companies: %s",
                ", ".join(ar_companies.mapped("name")),
            )

    @api.model
    def re_check_afip_currency_rate(self):
        """If afip provider and set interval unit daily then check the
        currency multiple times at day (in case the default odoo cron couldn't
        update the currency with AFIP). Also check for weekly and monthly
        interval units."""
        today = fields.Date.context_today(self.with_context(tz="America/Argentina/Buenos_Aires"))
        # Daily
        self._filter_recheck_afip_currency_rate_companies(
            currency_interval_unit="daily", l10n_ar_last_currency_sync_date=today
        )
        # Weekly
        last_seven_days = today - relativedelta(days=7)
        self._filter_recheck_afip_currency_rate_companies(
            currency_interval_unit="weekly",
            l10n_ar_last_currency_sync_date=last_seven_days,
            l10n_ar_force_create_rate=True,
        )
        # Monthly
        last_month = today - relativedelta(months=1)
        self._filter_recheck_afip_currency_rate_companies(
            currency_interval_unit="monthly", l10n_ar_last_currency_sync_date=last_month, l10n_ar_force_create_rate=True
        )

    def _filter_recheck_afip_currency_rate_companies(
        self, currency_interval_unit, l10n_ar_last_currency_sync_date, l10n_ar_force_create_rate=False
    ):
        """Filters companies that use the 'afip' currency provider and require a currency rate update,
        based on the provided interval unit and last sync date. If applicable, triggers the rate update."""
        self.search(
            [
                ("currency_provider", "=", "afip"),
                ("currency_interval_unit", "=", currency_interval_unit),
                "|",
                ("l10n_ar_last_currency_sync_date", "<", l10n_ar_last_currency_sync_date),
                ("l10n_ar_last_currency_sync_date", "=", False),
            ]
        ).with_context(l10n_ar_force_create_rate=l10n_ar_force_create_rate).update_currency_rates()

    def update_currency_rates(self):
        """When the first cron 'Currency: rate update' runs, we only need to update the rates for Argentine companies that have a daily update interval. If the interval is weekly or monthly, the rates will be updated in the second cron 'Currency: Re Check Afip Currency Rate'."""
        if not self.env.context.get("l10n_ar_force_create_rate"):
            self = self.filtered(lambda c: c.currency_interval_unit == "daily")
        super(ResCompany, self).update_currency_rates()

    def _parse_afip_data(self, available_currencies):
        """This method is used to update the currency rates using AFIP provider. Rates are given against AR"""
        res = {}
        currency_ars = self.env.ref("base.ARS")
        today = fields.Date.context_today(self.with_context(tz="America/Argentina/Buenos_Aires"))
        if currency_ars in available_currencies:
            res[currency_ars.name] = (1.0, today)
        available_currencies = available_currencies.filtered("l10n_ar_afip_code") - currency_ars
        rate_date = today

        valid_certificate = (
            self.env["certificate.certificate"]
            .search([("active", "=", True), ("date_end", ">=", today)])
            .filtered(lambda c: c.country_code == "AR")
        )
        if self.env.company.l10n_ar_afip_ws_crt_id in valid_certificate:
            # Dejamos self.env.company porque self puede ser un recordset de más de una compañía
            company = self.env.company
        else:
            company = valid_certificate[:1].company_id if valid_certificate else False
        if not company:
            _logger.log(25, "No pudimos encontrar compañía con certificados de AFIP validos")
            return False
        env_company = self.env.company
        self.env.company = company
        for currency in available_currencies:
            try:
                # Obtain the currencies to be updated
                _logger.log(25, "Connecting to AFIP to update the currency rates for %s", currency.name)

                # Do not pass company since we need to find the one that has certificate
                afip_date, rate = currency._l10n_ar_get_afip_ws_currency_rate()
                afip_date = datetime.strptime(afip_date, "%Y%m%d").date() + relativedelta(days=1)
                if afip_date == rate_date or self.env.context.get("l10n_ar_force_create_rate"):
                    res.update({currency.name: (1.0 / rate, rate_date)})
                    _logger.log(25, "Currency %s %s %s", currency.name, rate_date, rate)
                else:
                    raise UserError(
                        "Returned Afip rate is not today's rate (%s, %s vs %s, %s)"
                        % (afip_date.strftime("%A"), afip_date, rate_date.strftime("%A"), rate_date)
                    )
            except Exception as e:
                _logger.log(25, "Could not get rate for currency %s. This is what we get:\n%s", currency.name, e)
            else:
                for company in self.filtered(lambda x: x.currency_provider == "afip"):
                    company.l10n_ar_last_currency_sync_date = fields.Date.context_today(
                        self.with_context(tz="America/Argentina/Buenos_Aires")
                    )
        self.env.company = env_company
        return res or False

    def _generate_currency_rates(self, parsed_data):
        """Sobre escribimos este método para lograr dos cosas:

        1. Evitar sobre escribir una cotización en las compañías Argentinas. Odoo por defecto siempre que intenta
           sincronizar una tasa la sobre escribe. No queremos esto, si ya existe una tasa (se haya creado por 1er cron,
           2do cron, manual, o porque fue agregada con extra de porcentaje/recargo) no deben ser modificadas.
        2. Compañías argentinas: si una compañía tiene monto de recargo o porcentaje y otras compañías no entonces debe
           aplicarse dicho monto de recargo o porcentaje solamente a las compañías que lo tengan configurado.
        """
        currency_rate = self.env["res.currency.rate"]
        currency_object = self.env["res.currency"]
        ar_companies = self.filtered(lambda x: x.currency_provider == "afip")

        for company in ar_companies:
            new_parsed_data = parsed_data.copy()
            for currency, (rate, date_rate) in parsed_data.items():
                already_existing_rate = currency_rate.search(
                    [
                        ("currency_id", "=", currency_object.search([("name", "=", currency)]).id),
                        ("name", "=", date_rate),
                        ("company_id", "=", company.id),
                    ]
                )
                if currency == company.currency_id.name:
                    continue
                if already_existing_rate:
                    new_parsed_data.pop(currency)
                elif company.rate_surcharge or company.rate_perc:
                    rate = 1.0 / rate
                    rate = rate * (1.0 + (company.rate_perc or 0.0))
                    rate += company.rate_surcharge or 0.0
                    rate = 1.0 / rate
                    new_parsed_data[currency] = (rate, date_rate)
            super(ResCompany, company)._generate_currency_rates(new_parsed_data)
        super(ResCompany, self - ar_companies)._generate_currency_rates(parsed_data)
