##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    rate_perc = fields.Float(
        digits=(16, 4),
    )
    rate_surcharge = fields.Float(
        digits=(16, 4),
    )
    l10n_ar_last_currency_sync_date = fields.Date(string="ARCA Last Sync Date", readonly=True)

    def _l10n_ar_currency_today(self):
        return fields.Date.context_today(self.with_context(tz="America/Argentina/Buenos_Aires"))

    @api.model
    def re_check_arca_currency_rate(self):
        """Retry the ARCA rate update for the companies that did not get it yet
        (in case the default odoo cron couldn't update the currency with ARCA)"""
        today = self._l10n_ar_currency_today()
        self._filter_recheck_arca_currency_rate_companies(
            currency_interval_unit="daily", l10n_ar_last_currency_sync_date=today
        )
        self._filter_recheck_arca_currency_rate_companies(
            currency_interval_unit="weekly",
            l10n_ar_last_currency_sync_date=today - relativedelta(days=7),
            l10n_ar_force_create_rate=True,
        )
        self._filter_recheck_arca_currency_rate_companies(
            currency_interval_unit="monthly",
            l10n_ar_last_currency_sync_date=today - relativedelta(months=1),
            l10n_ar_force_create_rate=True,
        )

    def _filter_recheck_arca_currency_rate_companies(
        self, currency_interval_unit, l10n_ar_last_currency_sync_date, l10n_ar_force_create_rate=False
    ):
        self.search(
            [
                ("currency_provider", "=", "arca"),
                ("currency_interval_unit", "=", currency_interval_unit),
                "|",
                ("l10n_ar_last_currency_sync_date", "<", l10n_ar_last_currency_sync_date),
                ("l10n_ar_last_currency_sync_date", "=", False),
            ]
        ).with_context(l10n_ar_force_create_rate=l10n_ar_force_create_rate).update_currency_rates()

    def _l10n_ar_get_arca_rate_company(self):
        """Company used to connect to ARCA: one whose own ARCA certificate is valid, production first and
        then the current one. The rates are the same for every company."""
        companies = (
            self.env["res.company"]
            .search([("l10n_ar_afip_ws_crt_id", "!=", False), ("l10n_ar_afip_ws_key_id", "!=", False)])
            .filtered(lambda c: c.l10n_ar_afip_ws_crt_id.active and c.l10n_ar_afip_ws_crt_id.is_valid)
        )
        return companies.sorted(lambda c: (c.l10n_ar_afip_ws_environment != "production", c != self.env.company, c.id))[
            :1
        ]

    def _parse_arca_data(self, available_currencies):
        """Ask ARCA with a single company and one currency at a time, so an error in one currency does not
        stop the others, skipping the currencies without ARCA code. Only today's rates are kept, unless
        l10n_ar_force_create_rate is in context."""
        rate_date = fields.Date.to_string(self._l10n_ar_currency_today())
        currency_ars = self.env.ref("base.ARS")
        res = {currency_ars.name: (1.0, rate_date)}
        arca_currencies = available_currencies.filtered("l10n_ar_afip_code") - currency_ars
        if skipped := available_currencies - arca_currencies - currency_ars:
            _logger.info("Currencies without ARCA code skipped: %s", ", ".join(skipped.mapped("name")))
        if not arca_currencies:
            return res

        company = self._l10n_ar_get_arca_rate_company()
        if not company:
            _logger.info("No pudimos encontrar compañía con certificados de ARCA validos")
            return False

        force_create_rate = self.env.context.get("l10n_ar_force_create_rate")
        for currency in arca_currencies:
            try:
                # The native method connects with the env company of the currencies, not of self
                arca_res = super(ResCompany, company.with_company(company))._parse_arca_data(
                    currency.with_company(company)
                )
            except Exception as e:
                _logger.info("Could not get the ARCA rate for %s:\n%s", currency.name, e)
                continue
            if currency.name not in arca_res:
                continue
            rate, arca_date = arca_res[currency.name]
            if arca_date == rate_date or force_create_rate:
                res[currency.name] = (rate, rate_date)
            else:
                _logger.info(
                    "Returned ARCA rate for %s is not today's rate (%s vs %s)", currency.name, arca_date, rate_date
                )
        return res

    def _l10n_ar_set_last_currency_sync_date(self, parsed_data):
        """Mark the day as synced once the rates are created, only if there is today's rate for every
        active currency with ARCA code. Without foreign currencies it is not marked, so the retry cron
        takes a currency activated later in the day (it does not connect to ARCA meanwhile)."""
        rate_date = fields.Date.to_string(self._l10n_ar_currency_today())
        currencies = self.env["res.currency"].search([("l10n_ar_afip_code", "!=", False)]) - self.env.ref("base.ARS")
        if currencies and all(c.name in parsed_data and str(parsed_data[c.name][1]) == rate_date for c in currencies):
            self.l10n_ar_last_currency_sync_date = rate_date

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
        ar_companies = self.filtered(lambda x: x.currency_provider == "arca")

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
        ar_companies._l10n_ar_set_last_currency_sync_date(parsed_data)
