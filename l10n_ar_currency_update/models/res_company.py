##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging
from datetime import datetime

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
                ("parent_id", "=", False),
                ("currency_provider", "=", "arca"),
                ("currency_interval_unit", "=", currency_interval_unit),
                "|",
                ("l10n_ar_last_currency_sync_date", "<", l10n_ar_last_currency_sync_date),
                ("l10n_ar_last_currency_sync_date", "=", False),
            ]
        ).with_context(l10n_ar_force_create_rate=l10n_ar_force_create_rate).update_currency_rates()

    @api.model
    def _l10n_ar_set_arca_currency_provider(self):
        """On install, the native compute only sets the provider when the country changes"""
        self.search([("parent_id", "=", False)]).filtered(
            lambda c: c.country_id.code == "AR"
        ).currency_provider = "arca"

    def _l10n_ar_get_arca_rate_company(self):
        """Company used to connect to ARCA: one whose own ARCA certificate is valid, production first and
        then the current one. The rates are the same for every company."""
        companies = (
            self.env["res.company"]
            .search([("l10n_ar_afip_ws_crt_id", "!=", False), ("l10n_ar_afip_ws_key_id", "!=", False)])
            .filtered(
                lambda c: c.l10n_ar_afip_ws_crt_id.active
                and c.l10n_ar_afip_ws_crt_id.is_valid
                # ARCA authenticates with the CUIT of the company, so the certificate has to be its own
                and c.l10n_ar_afip_ws_crt_id.company_id == c
            )
        )
        return companies.sorted(lambda c: (c.l10n_ar_afip_ws_environment != "production", c != self.env.company, c.id))[
            :1
        ]

    @api.model
    def _l10n_ar_arca_currencies(self, currencies):
        """Currencies that are asked to ARCA: the ones with ARCA code, except ARS"""
        return currencies.filtered("l10n_ar_afip_code") - self.env.ref("base.ARS")

    def _parse_arca_data(self, available_currencies):
        """Ask ARCA with a single company and one connection, one currency at a time, so an error in one
        currency does not stop the others, skipping the currencies without ARCA code. Only today's rates
        are kept, unless l10n_ar_force_create_rate is in context."""
        rate_date = fields.Date.to_string(self._l10n_ar_currency_today())
        res = {self.env.ref("base.ARS").name: (1.0, rate_date)}
        arca_currencies = self._l10n_ar_arca_currencies(available_currencies)
        if skipped := available_currencies - arca_currencies - self.env.ref("base.ARS"):
            _logger.info("Currencies without ARCA code skipped: %s", ", ".join(skipped.mapped("name")))
        if not arca_currencies:
            return res

        company = self._l10n_ar_get_arca_rate_company()
        if not company:
            _logger.warning("No Argentinian company with a valid ARCA certificate to get the currency rates")
            return res
        try:
            client, auth = company._l10n_ar_get_connection("wsfe")._get_client()
        except Exception as e:
            _logger.warning("Could not connect to ARCA to get the currency rates:\n%s", e)
            return res

        force_create_rate = self.env.context.get("l10n_ar_force_create_rate")
        for currency in arca_currencies.with_company(company):
            try:
                arca_date, rate = currency._l10n_ar_get_afip_ws_currency_rate(client, auth)
            except Exception as e:
                _logger.warning("Could not get the ARCA rate for %s:\n%s", currency.name, e)
                continue
            if not rate:
                _logger.warning("ARCA returned no rate for %s", currency.name)
                continue
            # ARCA publishes the rate of a day to be used from the next one
            arca_date = fields.Date.to_string(datetime.strptime(arca_date, "%Y%m%d") + relativedelta(days=1))
            if arca_date == rate_date or force_create_rate:
                res[currency.name] = (1.0 / rate, rate_date)
            else:
                _logger.info(
                    "Returned ARCA rate for %s is not today's rate (%s vs %s)", currency.name, arca_date, rate_date
                )
        return res

    def _l10n_ar_set_last_currency_sync_date(self, parsed_data):
        """Mark the day as synced once the rates are created, when every active currency with ARCA code has
        that day's rate, from ARCA or already loaded. Without foreign currencies it is not marked, so the
        retry cron takes a currency activated later in the day (it does not connect to ARCA meanwhile)."""
        rate_date = str(parsed_data.get(self.env.ref("base.ARS").name, (None, ""))[1])
        currencies = self._l10n_ar_arca_currencies(self.env["res.currency"].search([]))
        if not rate_date or not currencies:
            return
        missing = currencies.filtered(lambda c: str(parsed_data.get(c.name, (None, ""))[1]) != rate_date)
        for company in self:
            loaded = (
                self.env["res.currency.rate"]
                .search([("currency_id", "in", missing.ids), ("company_id", "=", company.id), ("name", "=", rate_date)])
                .currency_id
            )
            if not missing - loaded:
                company.l10n_ar_last_currency_sync_date = rate_date

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
