/** @odoo-module **/

import { AccountImportGuide } from "@account_base_import/js/account_import_guide";
import { patch } from "@web/core/utils/patch";

patch(AccountImportGuide.prototype, {

    async _importSalesFromArca() {
        const config = await this.orm.call(
            "account.import.summary",
            "create",
            [{}]
        );
        const result = await this.orm.call(
            "account.import.summary",
            "action_import_sales_from_arca",
            [config]
        );
        this.actionService.doAction(result);
    },

    async _importPurchasesFromArca() {
        const config = await this.orm.call(
            "account.import.summary",
            "create",
            [{}]
        );
        const result = await this.orm.call(
            "account.import.summary",
            "action_import_purchases_from_arca",
            [config]
        );
        this.actionService.doAction(result);
    },

});
