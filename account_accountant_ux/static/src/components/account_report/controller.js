/** @odoo-module */
import { AccountReportController } from "@account_reports/components/account_report/controller";
import { patch } from "@web/core/utils/patch";

patch(AccountReportController.prototype, {
    async updateLines(lineIds, key, value) {
        super.updateLines(lineIds, key, value);

        // If no_followup changed, reload the report to update totals
        if (key === 'no_followup') {
            // Use reload instead of load to properly refresh the report data
            await this.reload('', this.options);
        }
    },
});
