/** @odoo-module **/

import { BankRecButtonList } from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import { patch } from "@web/core/utils/patch";

patch(BankRecButtonList.prototype, {
    /**
     * Always include the same_amount filter, and the posted filter when there is no partner
     */
    get bankRecSelectCreateDialogContext() {
        return {
            ...super.bankRecSelectCreateDialogContext,
            search_default_same_amount: 1,
            ...(this.statementLineData.partner_id ? {} : { search_default_posted: 1 }),
        };
    },

    get buttonsToDisplay() {
        const result = super.buttonsToDisplay;
        const buttons = this.buttons || {};

        // Add reconcile button when partner and account are shown
        if (buttons?.partner && buttons?.account && buttons?.reconcile) {
            result.push({ ...buttons.reconcile, primary: true });
        }

        return result;
    },
});
