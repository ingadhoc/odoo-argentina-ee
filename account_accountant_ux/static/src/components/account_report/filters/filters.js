/** @odoo-module **/

import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(AccountReportFilters.prototype, {
    get filterExtraOptionsData() {
        const data = super.filterExtraOptionsData;

        // Add the "Show All" filter option when require_custom_filter is enabled
        if (this.controller.filters.show_all_custom) {
            data['show_all_custom'] = {
                'name': _t("Show All"),
                'show': true,
            };
        }

        return data;
    },

    get selectedExtraOptions() {
        const selectedExtraOptions = super.selectedExtraOptions;
        const optionsArray = selectedExtraOptions ? selectedExtraOptions.split(", ") : [];

        // Add "Show All" status to the selected options display
        if (this.controller.filters.show_all_custom) {
            optionsArray.push(
                this.controller.cachedFilterOptions.show_all_custom
                    ? _t("Show All")
                    : _t("With Filters")
            );
        }

        return optionsArray.join(", ");
    },

    async filterClicked({ optionKey, optionValue = undefined, reload = false}) {
        // If toggling "Show All" option to true, clear all other filters
        if (optionKey === 'show_all_custom' && !this.controller.cachedFilterOptions.show_all_custom) {
            // Clear partner filters
            if (this.controller.options.partner_ids) {
                this.controller.options.partner_ids = [];
            }

            // Clear partner categories
            if (this.controller.options.selected_partner_categories) {
                this.controller.options.selected_partner_categories = null;
            }

            // Clear AML IR filters
            if (this.controller.options.aml_ir_filters) {
                this.controller.options.aml_ir_filters.forEach(filter => {
                    filter.selected = false;
                });
            }

            // Clear all extra filter options
            const extraOptions = this.filterExtraOptionsData;
            for (const option in extraOptions) {
                if (option !== 'show_all_custom' && this.controller.cachedFilterOptions[option]) {
                    this.controller.cachedFilterOptions[option] = false;
                }
            }
        }

        // If applying any other filter, disable "Show All" filter
        if (optionKey !== 'show_all_custom' && this.controller.cachedFilterOptions.show_all_custom) {
            // Check if a filter is actually being applied (not cleared)
            const isApplyingFilter = this._isApplyingFilter(optionKey, optionValue);

            if (isApplyingFilter) {
                this.controller.cachedFilterOptions.show_all_custom = false;
            }
        }

        // Call the parent method to toggle/update the option
        return super.filterClicked({ optionKey, optionValue, reload });
    },

    _isApplyingFilter(optionKey, optionValue) {
        // Check if a filter is being applied (not just cleared)
        if (optionKey === 'partner_ids') {
            return optionValue && optionValue.length > 0;
        }
        if (optionKey === 'selected_partner_categories') {
            return optionValue !== null;
        }
        if (optionKey === 'aml_ir_filters') {
            return optionValue && optionValue.some(filter => filter.selected);
        }
        // For boolean/toggle options, assume they're being applied if called
        return true;
    },
});
