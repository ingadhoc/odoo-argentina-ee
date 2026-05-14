/** @odoo-module **/

import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

const { DateTime } = luxon;

patch(AccountReportFilters.prototype, {
    /**
     * Rename "Year" → "Fiscal Year" and add new "Calendar Year" entry.
     */
    dateFilters(mode) {
        switch (mode) {
            case "single":
                return [
                    { name: _t("End of Month"), period: "month" },
                    { name: _t("End of Quarter"), period: "quarter" },
                    { name: _t("Fiscal Year"), period: "year" },
                    { name: _t("Calendar Year"), period: "calendar_year" },
                ];
            case "range":
                return [
                    { name: _t("Month"), period: "month" },
                    { name: _t("Quarter"), period: "quarter" },
                    { name: _t("Fiscal Year"), period: "year" },
                    { name: _t("Calendar Year"), period: "calendar_year" },
                ];
            default:
                throw new Error(`Invalid mode in dateFilters(): ${mode}`);
        }
    },

    /**
     * Include 'calendar_year' in the initial state and correctly restore it
     * from options coming from the backend.
     */
    initDateFilters() {
        const filters = {
            month: 0,
            quarter: 0,
            year: 0,
            calendar_year: 0,
            tax_period: 0,
        };

        const periodType = this.controller.options.date.period_type;
        const filter = this.controller.options.date.filter || "";
        const specifier = filter.split("_")[0];

        // Map 'fiscalyear' → 'year' (core behaviour).
        const period =
            periodType === "fiscalyear" ? "year" : periodType;

        if (period in filters) {
            filters[period] =
                this.controller.options.date.period ||
                (specifier === "previous" ? -1 : specifier === "next" ? 1 : 0);
        }

        return filters;
    },

    /**
     * Override to avoid a full reload when clicking the already-active "Fiscal Year"
     * filter. Core computes reload as `dateFilter.period != controller.options.date.period_type`,
     * but when Fiscal Year is active the backend returns period_type="fiscalyear" while
     * dateFilter.period is "year" — so the comparison is always true → reload=true →
     * the component re-mounts, collapsing all expanded Journal Items rows.
     *
     * Fix: compare filter strings directly. If the resulting filter key equals the current
     * one (same period type AND same navigation offset), no reload is needed — regardless
     * of what period_type the backend stored.
     */
    selectDateFilter(periodType, _reload = false) {
        const newFilter = this.getDateFilter(periodType);
        const currentFilter = this.controller.options.date.filter || "";
        const reload = newFilter !== currentFilter;
        this.filterClicked({ optionKey: "date.filter", optionValue: newFilter });
        this.filterClicked({ optionKey: "date.period", optionValue: this.dateFilter[periodType], reload: reload });
    },

    /**
     * Return the correct filter string for each period type.
     * Ensure 'calendar_year' is handled explicitly before falling
     * through to the generic implementation.
     */
    getDateFilter(periodType) {
        const offset = this.dateFilter[periodType];
        if (offset > 0) return `next_${periodType}`;
        if (offset === 0) return `this_${periodType}`;
        return `previous_${periodType}`;
    },

    /**
     * Highlight only the exact period type that is currently active.
     * Without this override, 'year' would also match inside 'calendar_year'.
     */
    isPeriodSelected(periodType) {
        const filter = this.controller.options.date.filter || "";
        if (periodType === "year") {
            return filter.includes("year") && !filter.includes("calendar_year");
        }
        return filter.includes(periodType);
    },

    /**
     * Display the human-readable label for each period type in the
     * navigation arrows area of the date filter dropdown.
     */
    displayPeriod(periodType) {
        const dateTo = DateTime.now();
        switch (periodType) {
            case "month":
                return this._displayMonth(dateTo);
            case "quarter":
                return this._displayQuarter(dateTo);
            case "year":
                return this._displayYear(dateTo);
            case "calendar_year":
                return this._displayCalendarYear(dateTo);
            case "tax_period":
                return this._displayTaxPeriod(dateTo);
            default:
                throw new Error(
                    `Invalid period type in displayPeriod(): ${periodType}`
                );
        }
    },

    /** Show the calendar year (e.g. "2025") offset by the current selection. */
    _displayCalendarYear(dateTo) {
        return dateTo
            .plus({ years: this.dateFilter.calendar_year })
            .toFormat("yyyy");
    },

    /**
     * Override _displayYear to show "YYYY - YYYY" for cross-calendar-year fiscal years.
     * Core shows just "2026", but companies with e.g. Sep-Aug FY expect "2025 - 2026".
     *
     * Strategy: use the backend-provided 'fiscal_year_current_string' (always present in
     * options.date regardless of the active filter) to detect cross-year FY companies.
     * This ensures the correct label shows in the Fiscal Year row even when Month,
     * Quarter or Calendar Year is the currently selected filter.
     */
    _displayYear(dateTo) {
        const offset = this.dateFilter.year;

        // fiscal_year_current_string is always set by the Python override and reflects
        // the actual current FY (today), e.g. "2025 - 2026" or plain "2026".
        const fyString = this.controller.options.date.fiscal_year_current_string || "";
        const crossYearMatch = fyString.match(/^(\d{4})\s*-\s*(\d{4})$/);
        if (crossYearMatch) {
            const year1 = parseInt(crossYearMatch[1]) + offset;
            const year2 = parseInt(crossYearMatch[2]) + offset;
            return `${year1} - ${year2}`;
        }

        return dateTo.plus({ years: offset }).toFormat("yyyy");
    },
});
