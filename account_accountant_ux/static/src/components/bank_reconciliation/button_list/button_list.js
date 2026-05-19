/** @odoo-module **/

import { BankRecButtonList } from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import { BankRecSelectCreateDialog } from "@account_accountant/components/bank_reconciliation/search_dialog/search_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(BankRecButtonList.prototype, {
    /**
     * Override the reconcileOnReconcileLine method to always include the same_amount filter
     */
    reconcileOnReconcileLine() {
        const context = {
            list_view_ref: "account_accountant.view_account_move_line_list_bank_rec_widget",
            search_view_ref: "account_accountant.view_account_move_line_search_bank_rec_widget",
            preferred_aml_value: -this.props.suspenseAccountLine.amount_currency,
            preferred_aml_currency_id: this.props.suspenseAccountLine.currency_id.id,
            // Always include the same_amount filter as default
            search_default_same_amount: 1,
            // Keep the original logic: partner filter if partner exists, posted filter otherwise
            ...(this.statementLineData.partner_id
                ? { search_default_partner_id: this.statementLineData.partner_id.id }
                : { search_default_posted: 1 }),
        };

        this.addDialog(
            BankRecSelectCreateDialog,
            {
                title: _t("Search: Journal Items to Match"),
                noCreate: true,
                domain: this.getReconcileButtonDomain(),
                resModel: "account.move.line",
                size: "xl",
                context: context,
                onSelected: async (moveLines) => {
                    await this.orm.call(
                        "account.bank.statement.line",
                        "set_line_bank_statement_line",
                        [this.statementLineData.id, moveLines]
                    );
                    await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
                        this.env.model.root.records
                    );
                    this.props.statementLine.load();
                    this.bankReconciliation.reloadChatter();
                    this.restoreFocus();
                },
                suspenseAccountLine: this.props.suspenseAccountLine,
                reference: this.statementLineData.payment_ref,
                date: this.statementLineData.date,
            },
            { onClose: () => this.restoreFocus() }
        );
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
