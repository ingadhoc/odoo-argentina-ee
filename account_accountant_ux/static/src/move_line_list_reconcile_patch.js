import { onMounted, useSubEnv } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import {
    AccountMoveLineReconcileListController,
    AccountMoveLineReconcileListRenderer,
} from "@account_accountant/components/move_line_list_reconcile/move_line_list_reconcile";

patch(AccountMoveLineReconcileListController.prototype, {
    setup() {
        super.setup();
        // The action service only passes a state when it restores the view (breadcrumbs).
        useSubEnv({ isReconcileListRestored: Boolean(this.props.state?.modelState) });
    },
});

patch(AccountMoveLineReconcileListRenderer.prototype, {
    setup() {
        // Unfold the first groups once mounted: a renderer dropped before mount must not load them.
        this.deferInitialUnfold = true;
        try {
            super.setup();
        } finally {
            this.deferInitialUnfold = false;
        }
        onMounted(() => {
            // A restored view keeps the groups the user folded or unfolded.
            if (this.env.isReconcileListRestored) {
                return;
            }
            for (const group of this.props.list.groups || []) {
                if (group.isFolded) {
                    super.toggleGroup(group);
                }
            }
        });
    },

    toggleGroup(group) {
        if (this.deferInitialUnfold) {
            return;
        }
        return super.toggleGroup(group);
    },
});
