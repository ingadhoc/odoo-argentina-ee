from collections import defaultdict

from odoo import _, fields, models
from odoo.addons.account_reports.utils.report_data_objects import AccountReportColumnData, AccountReportLineData


class AccountFollowupCustomHandler(models.AbstractModel):
    _inherit = "account.followup.report.handler"

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)
        return self._add_partner_total_lines(report, options, lines)

    def _add_partner_total_lines(self, report, options, lines):
        """Append Total Due / Total Overdue below each partner, summed from its move lines."""
        columns = options["columns"]
        residual_indexes = [i for i, col in enumerate(columns) if col["expression_label"] == "amount_residual"]
        if not residual_indexes:
            return lines
        index_by_label = defaultdict(dict)
        for i, col in enumerate(columns):
            index_by_label[col["expression_label"]][col["column_group_index"]] = i

        children_by_partner_line_id = defaultdict(list)
        last_child_position = {}
        paginated_partner_line_ids = set()
        for position, line in enumerate(lines):
            markup = report._get_markup(line.id)
            if markup == "load_more":
                paginated_partner_line_ids.add(line.parent_id)
            elif isinstance(markup, dict) and markup.get("groupby") == "id":
                children_by_partner_line_id[line.parent_id].append(line)
                last_child_position[line.parent_id] = position

        # With pagination the lines are partial: the totals come with the "load more" call, which returns them all.
        total_lines_by_position = {}
        today = fields.Date.context_today(report)
        for partner_line_id, children in children_by_partner_line_id.items():
            if partner_line_id in paginated_partner_line_ids:
                continue
            model, partner_id = report._get_model_info_from_id(partner_line_id)
            if model != "res.partner" or not partner_id:
                continue

            totals = {}
            for residual_index in residual_indexes:
                group_index = columns[residual_index]["column_group_index"]
                maturity_index = index_by_label["date_maturity"].get(group_index)
                no_followup_index = index_by_label["no_followup"].get(group_index)
                total_due = total_overdue = 0.0
                for child in children:
                    if no_followup_index is not None and child.columns[no_followup_index].no_format:
                        continue
                    amount = child.columns[residual_index].no_format or 0.0
                    total_due += amount
                    date_maturity = child.columns[maturity_index].no_format if maturity_index is not None else None
                    if date_maturity and date_maturity < today:
                        total_overdue += amount
                totals[residual_index] = (total_due, total_overdue)

            level = children[0].level
            total_lines_by_position[last_child_position[partner_line_id]] = [
                self._get_partner_total_line(
                    report,
                    options,
                    partner_line_id,
                    "total_due",
                    _("Total Due"),
                    {i: due for i, (due, _overdue) in totals.items()},
                    level,
                ),
                self._get_partner_total_line(
                    report,
                    options,
                    partner_line_id,
                    "total_overdue",
                    _("Total Overdue"),
                    {i: overdue for i, (_due, overdue) in totals.items()},
                    level,
                ),
            ]

        if not total_lines_by_position:
            return lines
        result = []
        for position, line in enumerate(lines):
            result.append(line)
            result.extend(total_lines_by_position.get(position, []))
        return result

    def _get_partner_total_line(self, report, options, partner_line_id, markup, name, amount_by_index, level):
        """Build a partner summary line showing the amounts in the residual columns."""
        return AccountReportLineData(
            id=report._get_generic_line_id(None, None, markup=markup, parent_line_id=partner_line_id),
            name=name,
            level=level,
            parent_id=partner_line_id,
            columns=[
                report._build_column_data(amount_by_index[i], column, options=options)
                if i in amount_by_index
                else AccountReportColumnData()
                for i, column in enumerate(options["columns"])
            ],
            css_class="total",
        )
