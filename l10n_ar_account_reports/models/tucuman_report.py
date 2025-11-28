# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class L10n_ArTucumanReportHandler(models.AbstractModel):
    _name = "l10n_ar.tucuman.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian Tucumán Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Datos",
                "sequence": 30,
                "action": "export_file",
                "action_param": "tucuman_datos_txt",
                "file_export_type": "TXT",
            },
            {
                "name": "TXT RETPER",
                "sequence": 30,
                "action": "export_file",
                "action_param": "tucuman_retper_txt",
                "file_export_type": "TXT",
            },
            {
                "name": "TXT NCFACT",
                "sequence": 30,
                "action": "export_file",
                "action_param": "tucuman_ncfact_txt",
                "file_export_type": "TXT",
            },
        ]
        options["buttons"].extend(txt_export_button)

    def tucuman_datos_txt(self, options):
        return {
            "file_name": "DATOS.txt",
            "file_content": self._tucuman_book_get_txt_files(options, file_type="datos"),
            "file_type": "txt",
        }

    def tucuman_retper_txt(self, options):
        return {
            "file_name": "RETPER.TXT",
            "file_content": self._tucuman_book_get_txt_files(options, file_type="retper"),
            "file_type": "txt",
        }

    def tucuman_ncfact_txt(self, options):
        return {
            "file_name": "NCFACT.TXT",
            "file_content": self._tucuman_book_get_txt_files(options, file_type="ncfact"),
            "file_type": "txt",
        }

    def _tucuman_book_get_txt_files(self, options, file_type):
        """Returns Tucumán txt content"""
        move_lines = self._tucuman_book_get_txt_lines(options, file_type)
        return "".join(self._get_tucuman_txt_content(move_lines)).encode("ISO-8859-1", "ignore")

    def _tucuman_book_get_txt_lines(self, options, file_type):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "=", "T"),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
            "|",
            ("tax_line_id.type_tax_use", "=", "sale"),
            ("tax_line_id.l10n_ar_withholding_payment_type", "=", "purchase"),
        ] + self._tucuman_book_get_lines_domain(options)

        # lo hacemos igual que está hoy, probablemente tengamos que hacer busqueda negativa para los otros casos?
        if file_type == "ncfact":
            domain += [("move_id.move_type", "=", "out_refund")]

        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _tucuman_book_get_lines_domain(self, options):
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

    def _get_tucuman_txt_content(self, move_lines):
        """Returns the lines to be printed in the txt file."""
        lines = []
        # TODO implementar
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""

            lines.append(content)
        return lines
