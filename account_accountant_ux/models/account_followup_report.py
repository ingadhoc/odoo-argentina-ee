from odoo import _, models


class FollowupReportCustomHandler(models.AbstractModel):
    _inherit = "account.followup.report.handler"

    def _get_report_line_move_line(
        self, options, aml_query_result, partner_line_id, init_bal_by_col_group, level_shift=0
    ):
        """Add amount_residual value to the line."""
        line = super()._get_report_line_move_line(
            options, aml_query_result, partner_line_id, init_bal_by_col_group, level_shift
        )
        line["amount_residual"] = aml_query_result.get("amount_residual", 0.0)
        return line

    def _get_partner_aml_report_lines(
        self, report, options, partner_line_id, aml_results, progress, offset=0, level_shift=0
    ):
        """Append Total Due / Total Overdue lines summed from the report's own aml_results."""
        lines, next_progress, treated_results_count, has_more = super()._get_partner_aml_report_lines(
            report, options, partner_line_id, aml_results, progress, offset, level_shift
        )

        # Render the total once, on the partner's last page (has_more=False).
        if has_more:
            return lines, next_progress, treated_results_count, has_more

        _dummy1, _dummy2, partner_id = report._parse_line_id(partner_line_id)[-1]
        if not partner_id:
            return lines, next_progress, treated_results_count, has_more

        # Single page (offset 0) → aml_results has every line; paginated → re-query the full set.
        partner_amls = aml_results if not offset else self._get_aml_values(options, [partner_id]).get(partner_id, [])

        followup_amls = [aml for aml in partner_amls if not aml.get("no_followup")]
        total_due = sum(aml["amount_residual"] for aml in followup_amls)
        total_overdue = sum(aml["amount_residual"] for aml in self._filter_overdue_amls_from_results(followup_amls))

        lines.append(
            self._get_partner_total_line(
                report, options, partner_line_id, "total_due", _("Total Due"), total_due, level_shift
            )
        )
        lines.append(
            self._get_partner_total_line(
                report, options, partner_line_id, "total_overdue", _("Total Overdue"), total_overdue, level_shift
            )
        )

        return lines, next_progress, treated_results_count, has_more

    def _get_partner_total_line(self, report, options, partner_line_id, markup, name, amount, level_shift):
        """Build a partner summary line showing ``amount`` in the last column."""
        last_index = len(options["columns"]) - 1
        columns = [
            report._build_column_dict(amount, column, options=options) if idx == last_index else {}
            for idx, column in enumerate(options["columns"])
        ]
        return {
            "id": report._get_generic_line_id(None, None, markup=markup, parent_line_id=partner_line_id),
            "name": name,
            "level": 3 + level_shift,
            "parent_id": partner_line_id,
            "columns": columns,
            "class": "total",
        }
