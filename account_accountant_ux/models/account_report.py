##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import datetime

from dateutil.relativedelta import relativedelta
from odoo import fields, models


class AccountReport(models.Model):
    _inherit = "account.report"

    require_custom_filter = fields.Boolean(
        help="If enabled, the report will not load data unless a custom filter or partner filter is applied.",
        default=False,
    )

    def _get_options_domain(self, options, date_scope):
        """Override to add a dummy domain if custom filter is required and no filters are applied."""
        domain = super()._get_options_domain(options, date_scope)

        if self.require_custom_filter:
            has_partner_filter = options.get("partner_ids") and len(options.get("partner_ids", [])) > 0
            has_aml_filter = False
            has_partner_categories_filter = options.get("selected_partner_categories")

            aml_ir_filters = options.get("aml_ir_filters", [])
            if aml_ir_filters:
                has_aml_filter = any(f.get("selected") for f in aml_ir_filters)

            if not has_partner_filter and not has_aml_filter and not has_partner_categories_filter:
                domain = [("id", "=", False)]

        return domain

    def _init_options_date(self, options, previous_options):
        """Override to:
        1. Support 'calendar_year' filter (01/01/YYYY – 31/12/YYYY).
        2. Fix Odoo core's curr_year advancement bug for cross-calendar-year FY companies:
           after super() sets dates, re-anchor fiscal-year filters to the FY containing today.
        3. Always expose 'fiscal_year_current_string' in options['date'] so the JS dropdown
           shows the correct "YYYY - YYYY" label in every row regardless of the active filter.
        """
        date = previous_options.get("date", {})
        date_filter = date.get("filter", "custom")
        options_mode = "range" if self.filter_date_range else "single"
        today = fields.Date.context_today(self)
        # Pre-compute the actual current FY once; used for the fix and the JS label.
        fy_dates = self.env.company.compute_fiscalyear_dates(today)
        fy_base = self._get_dates_period(fy_dates["date_from"], fy_dates["date_to"], options_mode)

        if "calendar_year" in date_filter:
            period = date.get("period", 0) or 0
            year = today.year + period
            options["date"] = self._get_dates_period(
                datetime.date(year, 1, 1),
                datetime.date(year, 12, 31),
                options_mode,
                period_type="calendar_year",
            )
            options["date"]["filter"] = date_filter
            options["date"]["period"] = period
        else:
            super()._init_options_date(options, previous_options)
            # Fix: core advances cross-calendar-year FY companies to a future FY when
            # date_from.year < today.year. Re-anchor to the FY that actually contains today.
            if "year" in options.get("date", {}).get("filter", ""):
                period = options["date"].get("period", 0) or 0
                corrected = fy_base if period == 0 else self._get_shifted_dates_period(options, fy_base, period)
                options["date"].update(
                    {
                        "date_from": corrected["date_from"],
                        "date_to": corrected["date_to"],
                        "string": corrected.get("string", ""),
                    }
                )

        if "date" in options:
            options["date"]["fiscal_year_current_string"] = fy_base.get("string", "")

    def _get_dates_period(self, date_from, date_to, mode, period_type=None):
        """Override to handle 'calendar_year' period type and show just the year as label."""
        result = super()._get_dates_period(date_from, date_to, mode, period_type=period_type)
        if period_type == "calendar_year" and date_to:
            result["string"] = date_to.strftime("%Y")
        return result

    def _get_shifted_dates_period(self, options, period_vals, periods, tax_period=False):
        """Override to handle period shifting for 'calendar_year' period type."""
        if period_vals.get("period_type") == "calendar_year":
            mode = period_vals["mode"]
            date_from = fields.Date.from_string(period_vals["date_from"])
            new_date_from = date_from + relativedelta(years=periods)
            new_date_to = datetime.date(new_date_from.year, 12, 31)
            return self._get_dates_period(new_date_from, new_date_to, mode, period_type="calendar_year")
        return super()._get_shifted_dates_period(options, period_vals, periods, tax_period=tax_period)
