/** @odoo-module **/

import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { patch } from "@web/core/utils/patch";

/**
 * Patch AccountReportFilters to handle sub-monthly periods like fortnightly.
 *
 * When months_per_period is 0 (for sub-monthly periods), the original JS code
 * fails with division by zero errors. This patch prevents those errors by:
 * 1. Not displaying the return_period filter for sub-monthly periods
 * 2. Falling back to month display if months_per_period is 0
 */
patch(AccountReportFilters.prototype, {
    /**
     * Override to hide return period filter for sub-monthly periods.
     * When months_per_period is 0, we don't want to show the return_period
     * selector as it would cause JS errors.
     */
    get shouldDisplayReturnPeriod() {
        const periodicitySettings = this.controller.cachedFilterOptions.return_periodicity;
        if (periodicitySettings) {
            // Don't display return period for sub-monthly periods (months_per_period === 0)
            if (!periodicitySettings.months_per_period || periodicitySettings.months_per_period === 0) {
                return false;
            }
            return periodicitySettings.start_day !== 1 || periodicitySettings.start_month !== 1 || ![1, 3, 12].includes(periodicitySettings.months_per_period);
        }
        return false;
    },

    /**
     * Override to handle sub-monthly periods safely.
     * Falls back to month display if months_per_period is 0.
    */
    displayPeriod(periodType) {
        if (periodType === "return_period") {
            const periodicitySettings = this.controller.cachedFilterOptions.return_periodicity;
            // Fall back to month for sub-monthly periods to avoid division by zero
            if (!periodicitySettings || !periodicitySettings.months_per_period || periodicitySettings.months_per_period === 0) {
                periodType = "month";
            }
        }
        return super.displayPeriod(periodType);
    },
});
