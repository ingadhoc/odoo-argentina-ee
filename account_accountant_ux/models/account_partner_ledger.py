import csv
import datetime
import io

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_repr

CSV_PARTNER_BATCH_SIZE = 200
# Leading characters that make a spreadsheet read a cell as a formula.
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = "account.partner.ledger.report.handler"

    def _custom_options_initializer(self, report, options, previous_options):
        """Add a CSV export, the one format that fits a fully unfolded ledger of a big period.

        The XLSX of the whole year, unfolded, does not fit in a worker: it builds every line
        of every partner in memory before writing the file. The CSV streams partner by partner,
        so it is also offered by "Copy to Documents" and can run in background.
        The follow-up and customer statement handlers inherit from this one: they keep their
        own buttons.
        """
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if self._name == "account.partner.ledger.report.handler":
            options["buttons"].append(
                {
                    "name": _("CSV"),
                    "sequence": 50,
                    "action": "export_file",
                    "action_param": "generate_csv_export",
                    "file_export_type": _("CSV"),
                    "branch_allowed": True,
                }
            )

    def open_journal_items(self, options, params):
        # Modificamos las vistas para que use las nuestras de account_ux en vez de las de partner grouped
        res = super().open_journal_items(options, params)
        res["search_view_id"] = [self.env.ref("account_ux.view_account_partner_ledger_filter").id, "search"]
        res["views"] = [(self.env.ref("account.view_move_line_payment_tree").id, "list")]
        res.get("context", {}).update({"search_default_group_by_partner": 1})
        return res

    def _get_partner_ledger_query(self, options, date_scope, match_partner_on_partials=True):
        # Core drops options['partner_ids'] before building the domain, so our
        # require_custom_filter override sees no partner filter and blanks the
        # domain, returning zero lines. We already know the partners, so
        # bypass the gate like "Show All" would.
        report = self.env["account.report"].browse(options.get("report_id"))
        if report.require_custom_filter and (options.get("partner_ids") or "partner_ledger_expand_partner" in options):
            options = {**options, "show_all_custom": True}
        return super()._get_partner_ledger_query(
            options, date_scope, match_partner_on_partials=match_partner_on_partials
        )

    def generate_csv_export(self, options):
        if len(options["column_groups"]) > 1:
            raise UserError(_("CSV export only works with one column group"))

        report = self.env["account.report"].browse(options["report_id"])
        return {
            "file_content": self._generate_csv_lazy_export(options),
            "file_type": "csv",
            "file_name": report.get_default_report_filename(options, "csv"),
        }

    def _generate_csv_lazy_export(self, options):
        """Yield the partner ledger fully unfolded, one batch of partners at a time.

        The lines are the ones the report shows (same builders), so the file matches the
        screen; only a batch of partners lives in memory at once.
        """
        with self.pool.cursor() as new_cr:
            self.env.flush_all()
            handler = self.with_env(self.env(cr=new_cr))
            options = handler._get_csv_export_options(options)
            partner_lines, total_line = handler._get_csv_partner_lines(options)
            yield handler._get_csv_header(options)
            for batch in handler._get_csv_partner_batches(partner_lines):
                yield from handler._get_csv_partner_rows(options, partner_lines, batch)
                handler.env.invalidate_all()
            yield handler._get_csv_total_row(options, total_line)

    def _get_bg_export_chunks(self, options, file_generator):
        """Split an export in parts that background jobs can build one by one.

        Hook read by ``documents_account_bg``: each part is built in a job of its own by
        ``_get_bg_export_chunk``, and the parts are joined in that order in one file.
        Only the CSV is split: one part per batch of partners.

        :return: ``None`` when the export is not split, else a dict with the ``file_name``
            and the ``chunks``, JSON-serializable payloads for ``_get_bg_export_chunk``.
        """
        if file_generator != "generate_csv_export":
            return None
        if len(options["column_groups"]) > 1:
            raise UserError(_("CSV export only works with one column group"))
        self.env.flush_all()
        report = self.env["account.report"].browse(options["report_id"])
        partner_lines, _totals = self._get_csv_partner_lines(self._get_csv_export_options(options))
        batches = self._get_csv_partner_batches(partner_lines) or [[]]
        chunks = [{"partner_ids": batch, "header": False, "total": False} for batch in batches]
        chunks[0]["header"] = chunks[-1]["total"] = True
        return {"file_name": report.get_default_report_filename(options, "csv"), "chunks": chunks}

    def _get_bg_export_chunk(self, options, file_generator, payload):
        """Build one part of the export split by ``_get_bg_export_chunks``, as bytes."""
        self.env.flush_all()
        options = self._get_csv_export_options(options)
        partner_lines, total_line = self._get_csv_partner_lines(options)
        rows = []
        if payload["header"]:
            rows.append(self._get_csv_header(options))
        rows.extend(self._get_csv_partner_rows(options, partner_lines, payload["partner_ids"]))
        if payload["total"]:
            rows.append(self._get_csv_total_row(options, total_line))
        return b"".join(rows)

    def _get_csv_export_options(self, options):
        report = self.env["account.report"].browse(options["report_id"])
        # "print" mode: no "load more" limit on the lines of a partner.
        return report.get_options(
            previous_options={**options, "export_mode": "print", "unfold_all": False, "unfolded_lines": []}
        )

    def _get_csv_partner_lines(self, options):
        """Return the partner lines by partner id (``None`` for "Unknown Partner"), and the total line."""
        report = self.env["account.report"].browse(options["report_id"])
        lines_by_partner_id = {}
        total_line = None
        for line in report.with_context(no_format=True)._get_lines(options):
            markup, model, res_id = report._parse_line_id(line.id)[-1]
            if markup == "total":
                # The total of the section, not the one under each unfolded partner.
                if report._parse_line_id(line.parent_id)[-1][1] == "account.report.line":
                    total_line = line
            elif model == "res.partner":
                lines_by_partner_id[res_id or None] = line
        return lines_by_partner_id, total_line

    def _get_csv_partner_batches(self, partner_lines):
        """Group the partners in batches, in the order of the report.

        The lines without partner get the reverse of every reconciled line of the other
        partners: only right when queried alone.
        """
        batches = []
        for partner_id in partner_lines:
            if partner_id is None:
                batches.append([None])
            elif batches and batches[-1] != [None] and len(batches[-1]) < CSV_PARTNER_BATCH_SIZE:
                batches[-1].append(partner_id)
            else:
                batches.append([partner_id])
        return batches

    def _get_csv_partner_rows(self, options, partner_lines, partner_ids):
        """Yield the rows of these partners: their line, then their lines unfolded."""
        report = self.env["account.report"].browse(options["report_id"]).with_context(no_format=True)
        for partner_id in partner_ids:
            # A partner may have left the report since the batches were made (background export).
            partner_line = partner_lines.get(partner_id)
            if not partner_line:
                continue
            yield self._get_csv_row(options, partner_line.name, partner_line)
            if not partner_line.unfoldable:
                continue
            # Same entry point as unfolding on screen: the handler post-processes the lines.
            expanded = report.get_expanded_lines(
                options,
                partner_line.id,
                partner_line.groupby,
                partner_line.expand_function,
                partner_line.horizontal_split_side,
                None,
                ignore_load_more=True,
            )
            for line in expanded:
                yield self._get_csv_row(options, partner_line.name, line)

    def _get_csv_header(self, options):
        header = [_("Partner"), _("Name")]
        for col in options["columns"]:
            if col["expression_label"] == "amount_currency":
                header += [_("Amount Currency"), _("Currency")]
            else:
                header.append(col["name"])
        return self._csv_format(header)

    def _get_csv_total_row(self, options, total_line):
        return self._get_csv_row(options, "", total_line) if total_line else b""

    def _get_csv_row(self, options, partner_name, line):
        company_currency = self.env.company.currency_id
        cells = [
            self._csv_escape_text(partner_name),
            self._csv_escape_text(line.name) if line.name != partner_name else "",
        ]
        # The label comes from the report column: the empty cells the ledger builds for a
        # missing value carry none, and "amount_currency" would then take one cell instead of
        # two, shifting the rest of the row.
        for report_col, col in zip(options["columns"], line.columns, strict=True):
            value = col.no_format
            currency = col.currency or company_currency
            if report_col["expression_label"] == "amount_currency":
                if value in (None, "") or currency == company_currency:
                    cells += ["", ""]
                else:
                    cells += [float_repr(value, currency.decimal_places), currency.name]
                continue
            if value is None:
                value = ""
            elif report_col["figure_type"] == "monetary" and isinstance(value, float):
                value = float_repr(value, currency.decimal_places)
            elif isinstance(value, datetime.date):
                value = value.isoformat()
            elif isinstance(value, str):
                value = self._csv_escape_text(value)
            cells.append(value)
        return self._csv_format(cells)

    def _csv_escape_text(self, value):
        """Keep a text typed by users (partner, label, reference) from running as a formula.

        Like the native list export: a leading quote, only on texts, never on the amounts
        (a negative balance starts with "-" too).
        """
        if isinstance(value, str) and value.startswith(CSV_FORMULA_PREFIXES):
            return "'" + value
        return value

    def _csv_format(self, cells):
        with io.StringIO() as buf:
            csv.writer(buf, delimiter=",", lineterminator="\n").writerow(cells)
            return buf.getvalue().encode()
