/** @odoo-module **/

import { AccountImportGuide } from "@account_base_import/js/account_import_guide";
import { patch } from "@web/core/utils/patch";

patch(AccountImportGuide.prototype, {

    async _openCheckBalanceImport() {
        const config = await this.orm.call(
            "account.import.summary",
            "create",
            [{}]
        );
        const result = await this.orm.call(
            "account.import.summary",
            "action_open_check_balance_import",
            [config]
        );
        this.actionService.doAction(result);
    },

});
