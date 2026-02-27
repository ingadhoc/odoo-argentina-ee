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
        """Override to add total_due line at the end."""
        lines, next_progress, treated_results_count, has_more = super()._get_partner_aml_report_lines(
            report, options, partner_line_id, aml_results, progress, offset, level_shift
        )

        # Get the partner from the line_id
        _dummy1, _dummy2, partner_id = report._parse_line_id(partner_line_id)[-1]
        if partner_id:
            partner = self.env["res.partner"].browse(partner_id)

            # Use partner.total_due which updates automatically when no_followup changes
            total_due = partner.total_due

            # Create a line for total_due
            total_due_line = {
                "id": report._get_generic_line_id(None, None, markup="total_due", parent_line_id=partner_line_id),
                "name": _("Total Due"),
                "level": 3 + level_shift,
                "parent_id": partner_line_id,
                "columns": [],
                "class": "total",
            }

            # Add empty columns for all except the last one
            for idx, column in enumerate(options["columns"]):
                if idx == len(options["columns"]) - 1:
                    # Last column shows the total_due amount
                    total_due_line["columns"].append(report._build_column_dict(total_due, column, options=options))
                else:
                    # Empty columns
                    total_due_line["columns"].append({})

            lines.append(total_due_line)
            # Also add a total_overdue line below total_due
            total_overdue = partner.total_overdue

            total_overdue_line = {
                "id": report._get_generic_line_id(None, None, markup="total_overdue", parent_line_id=partner_line_id),
                "name": _("Total Overdue"),
                "level": 3 + level_shift,
                "parent_id": partner_line_id,
                "columns": [],
                "class": "total",
            }

            for idx, column in enumerate(options["columns"]):
                if idx == len(options["columns"]) - 1:
                    total_overdue_line["columns"].append(
                        report._build_column_dict(total_overdue, column, options=options)
                    )
                else:
                    total_overdue_line["columns"].append({})

            lines.append(total_overdue_line)

        return lines, next_progress, treated_results_count, has_more
