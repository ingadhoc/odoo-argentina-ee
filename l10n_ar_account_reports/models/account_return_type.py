##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import datetime

from dateutil.relativedelta import relativedelta
from odoo import fields, models
from odoo.tools.misc import format_date

# Extended periods to include fortnightly (quincenal) for Argentina
L10N_AR_PERIODS = [
    ("fortnightly", "Fortnightly"),  # Quincenal
]

# Days per period for sub-monthly periodicities
L10N_AR_DAYS_PER_PERIOD = {
    "fortnightly": 15,
}


class AccountReturnType(models.Model):
    _inherit = "account.return.type"

    deadline_periodicity = fields.Selection(
        selection_add=L10N_AR_PERIODS,
    )
    default_deadline_periodicity = fields.Selection(
        selection_add=L10N_AR_PERIODS,
    )

    def _get_periodicity_months_delay(self, company):
        """Returns the number of months separating two returns.
        For sub-monthly periods (like fortnightly), returns 0.
        Use _get_periodicity_days_delay for sub-monthly periods.
        """
        self.ensure_one()
        periodicity = self._get_periodicity(company)
        if periodicity in L10N_AR_DAYS_PER_PERIOD:
            return 0
        return super()._get_periodicity_months_delay(company)

    def _get_periodicity_days_delay(self, company):
        """Returns the number of days separating two returns for sub-monthly periods.
        Returns 0 for monthly or longer periods.
        """
        self.ensure_one()
        periodicity = self._get_periodicity(company)
        return L10N_AR_DAYS_PER_PERIOD.get(periodicity, 0)

    def _is_sub_monthly_period(self, company):
        """Returns True if the periodicity is sub-monthly (e.g., fortnightly)"""
        self.ensure_one()
        return self._get_periodicity(company) in L10N_AR_DAYS_PER_PERIOD

    def _get_period_boundaries(self, company_id, date, override_period_months=None, override_start_date=None):
        """Returns the boundaries of the period containing the provided date
        for this return type as a tuple (start, end).

        Extended to support sub-monthly periods like fortnightly.
        """
        self.ensure_one()

        # Check if this is a sub-monthly period (e.g., fortnightly)
        if self._is_sub_monthly_period(company_id) and not override_period_months:
            return self._get_sub_monthly_period_boundaries(company_id, date, override_start_date)

        return super()._get_period_boundaries(company_id, date, override_period_months, override_start_date)

    def _get_sub_monthly_period_boundaries(self, company_id, date, override_start_date=None):
        """Returns the boundaries for sub-monthly periods like fortnightly.
        For fortnightly periods:
        - First fortnight: day 1 to day 15 of the month
        - Second fortnight: day 16 to last day of the month

        :param company_id: the company for which to compute the boundaries
        :param date: the date for which we want to find the period
        :param override_start_date: optional start date override
        :return: tuple (start_date, end_date)
        """
        self.ensure_one()
        periodicity = self._get_periodicity(company_id)

        if periodicity == "fortnightly":
            day = date.day
            year = date.year
            month = date.month

            if day <= 15:
                # First fortnight: 1st to 15th
                start_date = datetime.date(year, month, 1)
                end_date = datetime.date(year, month, 15)
            else:
                # Second fortnight: 16th to end of month
                start_date = datetime.date(year, month, 16)
                # Get last day of month
                end_date = datetime.date(year, month, 1) + relativedelta(months=1, days=-1)

            return start_date, end_date

        # Fallback for other sub-monthly periods (if added in future)
        days_per_period = self._get_periodicity_days_delay(company_id)
        if days_per_period <= 0:
            # Should not happen, but fallback to monthly
            return super()._get_period_boundaries(
                company_id, date, override_period_months=1, override_start_date=override_start_date
            )

        # Generic sub-monthly calculation based on days
        if override_start_date:
            start_day = override_start_date.day
        else:
            start_day, _ = self._get_start_date_elements(company_id)

        # Calculate period number within the month
        day_offset = date.day - start_day
        period_number = day_offset // days_per_period

        start_date = datetime.date(date.year, date.month, start_day) + relativedelta(
            days=period_number * days_per_period
        )
        end_date = start_date + relativedelta(days=days_per_period - 1)

        # Ensure end_date doesn't exceed month boundary
        month_end = datetime.date(date.year, date.month, 1) + relativedelta(months=1, days=-1)
        if end_date > month_end:
            end_date = month_end

        return start_date, end_date

    def _get_period_name(self, main_company, period_from=None, period_to=None, minimal=False, lang_code=None):
        """Extended to support fortnightly period names."""
        periodicity = self._get_periodicity(main_company)

        if period_from and period_to and periodicity == "fortnightly":
            # For fortnightly: show "1ra Quincena Mes Año" or "2da Quincena Mes Año"
            fortnight_num = 1 if period_from.day == 1 else 2
            month_name = format_date(self.env, period_from, date_format="LLLL", lang_code=lang_code)
            if minimal:
                # Short format: "1Q Dec" or "2Q Dec"
                month_short = format_date(self.env, period_from, date_format="LLL", lang_code=lang_code)
                return f"{fortnight_num}Q {month_short}"
            else:
                # Full format: "1ra Quincena Diciembre 2024" or "2da Quincena Diciembre 2024"
                ordinal = "1ra" if fortnight_num == 1 else "2da"
                return f"{ordinal} Quincena {month_name} {period_from.year}"

        return super()._get_period_name(main_company, period_from, period_to, minimal, lang_code)

    # @api.model
    # def _generate_all_returns(self, country_code, main_company, tax_unit=None):
    #     rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

    #     if country_code == "AR":
    #         ar_sales_return_type = self.env.ref("l10n_ar_account_reports.ar_pba_iibb_return_type")
    #         # Handle both monthly and sub-monthly periods (like fortnightly)
    #         if ar_sales_return_type._is_sub_monthly_period(main_company):
    #             period_days = ar_sales_return_type._get_periodicity_days_delay(main_company)
    #             date_in_previous_period = fields.Date.context_today(self) - relativedelta(days=period_days)
    #         else:
    #             offset = ar_sales_return_type._get_periodicity_months_delay(main_company)
    #             date_in_previous_period = fields.Date.context_today(self) - relativedelta(months=offset)
    #         date_from, date_to = ar_sales_return_type._get_period_boundaries(main_company, date_in_previous_period)
    #         tax_ids = self.env["account.tax"].filtered(lambda x: x.l10n_ar_state_id.country_id.code == "AR")

    #         domain = [
    #             ("tax_ids", "in", tax_ids),
    #             ("balance", "!=", 0),
    #             ("date", ">=", date_from),
    #             ("date", "<=", date_to),
    #             ("parent_state", "=", "posted"),
    #         ]
    #         if self.env["account.move.line"].search_count(domain, limit=1):
    #             ar_sales_return_type._try_create_return_for_period(date_from, main_company, tax_unit)

    #     return rslt
