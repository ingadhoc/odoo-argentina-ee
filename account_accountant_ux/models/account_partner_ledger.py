from odoo import models
from odoo.tools import SQL


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = "account.partner.ledger.report.handler"

    def open_journal_items(self, options, params):
        # Modificamos las vistas para que use las nuestras de account_ux en vez de las de partner grouped
        res = super().open_journal_items(options, params)
        res["search_view_id"] = [self.env.ref("account_ux.view_account_partner_ledger_filter").id, "search"]
        res["views"] = [(self.env.ref("account.view_move_line_payment_tree").id, "list")]
        res.get("context", {}).update({"search_default_group_by_partner": 1})
        return res

    def _get_additional_column_aml_values(self):
        """Add amount_residual to the query."""
        return SQL(
            "%s account_move_line.amount_residual AS amount_residual,", super()._get_additional_column_aml_values()
        )

    def _get_report_line_move_line(
        self, options, aml_query_result, partner_line_id, init_bal_by_col_group, level_shift=0
    ):
        """Add amount_residual value to the line."""
        line = super()._get_report_line_move_line(
            options, aml_query_result, partner_line_id, init_bal_by_col_group, level_shift
        )
        line["amount_residual"] = aml_query_result.get("amount_residual", 0.0)
        return line
