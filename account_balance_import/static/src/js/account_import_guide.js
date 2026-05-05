/** @odoo-module **/

import { AccountImportGuide } from "@account_base_import/js/account_import_guide";
import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";

patch(AccountImportGuide.prototype, {

    setup() {
        super.setup();
        onWillStart(async () => {
            // Cargar el asiento de apertura de la compañía
            const companyId = user.activeCompany.id;
            const company = await this.orm.read(
                "res.company",
                [companyId],
                ["account_opening_move_id", "country_id"]
            );
            this.accountOpeningMoveId = company[0].account_opening_move_id;
            // Load country code to conditionally show ARCA connection
            const countryId = company[0].country_id;
            if (countryId) {
                const country = await this.orm.read(
                    "res.country",
                    [countryId[0]],
                    ["code"]
                );
                this.companyCountryCode = country[0].code;
            } else {
                this.companyCountryCode = null;
            }
        });
    },

    async _openCompanyDataSetup() {
        const config = await this.orm.call(
            "account.import.summary",
            "create",
            [{}]
        );
        const result = await this.orm.call(
            "account.import.summary",
            "action_open_company_data_setup",
            [config]
        );
        this.actionService.doAction(result);
    },

    async _openFiscalYearSetup() {
        const config = await this.orm.call(
            "account.import.summary",
            "create",
            [{}]
        );
        const result = await this.orm.call(
            "account.import.summary",
            "action_open_fiscal_year_setup",
            [config]
        );
        this.actionService.doAction(result);
    },

    async _openJournalDashboard() {
        const config = await this.orm.call(
            "account.import.summary",
            "create",
            [{}]
        );
        const result = await this.orm.call(
            "account.import.summary",
            "action_open_journal_dashboard",
            [config]
        );
        this.actionService.doAction(result);
    },

    async _openArcaJournalWizard() {
        const config = await this.orm.call(
            "account.import.summary",
            "create",
            [{}]
        );
        const result = await this.orm.call(
            "account.import.summary",
            "action_open_arca_journal_wizard",
            [config]
        );
        this.actionService.doAction(result);
    },

    async _openPartnerBalanceImport() {
        const config = await this.orm.call(
            "account.import.summary",
            "create",
            [{}]
        );
        const result = await this.orm.call(
            "account.import.summary",
            "action_open_partner_balance_import",
            [config]
        );
        this.actionService.doAction(result);
    },

    async _openAccountOpeningMove() {
        if (this.accountOpeningMoveId) {
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "account.move",
                res_id: this.accountOpeningMoveId[0],
                views: [[false, "form"]],
                view_mode: "form",
                target: "current",
            });
        }
    },

    async _openArcaConnectionSetup() {
        const config = await this.orm.call(
            "account.import.summary",
            "create",
            [{}]
        );
        const result = await this.orm.call(
            "account.import.summary",
            "action_open_arca_connection_setup",
            [config]
        );
        this.actionService.doAction(result);
    },

});
