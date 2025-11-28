# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class L10n_ArMisionesReportHandler(models.AbstractModel):
    _name = "l10n_ar.misiones.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian Misiones Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "misiones_ret_txt",
                "file_export_type": "TXT",
            },
            {
                "name": "TXT Percepciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "misiones_perc_txt",
                "file_export_type": "TXT",
            },
        ]
        options["buttons"].extend(txt_export_button)

    def misiones_ret_txt(self, options):
        return {
            "file_name": "Retenciones IIBB Misiones.txt",
            "file_content": self._misiones_book_get_txt_files(options, "ret"),
            "file_type": "txt",
        }

    def misiones_perc_txt(self, options):
        return {
            "file_name": "Percepciones Misiones.txt",
            "file_content": self._misiones_book_get_txt_files(options, "perc"),
            "file_type": "txt",
        }

    def _misiones_book_get_txt_files(self, options, file_type):
        """Returns Misiones txt content"""
        move_lines = self._misiones_book_get_txt_lines(options, file_type)
        return "".join(self._get_misiones_txt_content(move_lines)).encode("ISO-8859-1", "ignore")

    def _misiones_book_get_txt_lines(self, options, file_type):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "=", "B"),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
        ] + self._pba_book_get_lines_domain(options)

        if file_type == "ret":
            domain += [("tax_line_id.l10n_ar_withholding_payment_type", "=", "purchase")]
        elif file_type == "perc":
            domain += [("tax_line_id.type_tax_use", "=", "sale")]

        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _misiones_book_get_lines_domain(self, options):
        company_ids = self.env.company.ids
        domain = [("company_id", "in", company_ids)]
        state = options.get("all_entries") and "all" or "posted"
        if state and state.lower() != "all":
            domain += [("move_id.state", "=", state)]
        if options.get("date").get("date_to"):
            domain += [("date", "<=", options["date"]["date_to"])]
        if options.get("date").get("date_from"):
            domain += [("date", ">=", options["date"]["date_from"])]
        return domain

    def _get_misiones_txt_content(self, move_lines):
        """Returns the lines to be printed in the txt file."""
        lines = []
        # TODO implementar
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""

            lines.append(content)
        return lines
