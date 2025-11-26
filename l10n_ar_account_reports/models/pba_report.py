# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class L10n_ArPbaReportHandler(models.AbstractModel):
    _name = "l10n_ar.pba.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian PBA Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones (excepto actividad 29, 7 quincenal, 7 y 17 de Bancos)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_ret_txt",
                "file_export_type": "TXT",
            },
            {
                "name": "TXT Percepciones (excepto actividad 29, 7 quincenal, 7 y 17 de Bancos)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_perc_txt",
                "file_export_type": "TXT",
            },
            {
                "name": "TXT Percepciones Act. 7 método Percibido (quincenal)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_perc_act_7_txt",
                "file_export_type": "TXT",
            },
        ]
        options["buttons"].extend(txt_export_button)

    def pba_ret_txt(self, options):
        period = 1
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "6",  # 6 serian las retenciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_book_get_txt_files(options, "ret"),
            "file_type": "txt",
        }

    def pba_perc_txt(self, options):
        period = 1
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "7",  # 7 serian las percepciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_book_get_txt_files(options, "perc"),
            "file_type": "txt",
        }

    def pba_perc_act_7_txt(self, options):
        period = 1
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat,
            period,
            "7",  # 7 serian las percepciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_book_get_txt_files(options, "perc_act_7"),
            "file_type": "txt",
        }

    def _pba_book_get_txt_files(self, options, type):
        """Returns PBA txt content"""
        move_lines = self._pba_book_get_txt_lines(options)
        return "".join(self._get_pba_txt_content(move_lines, type)).encode("ISO-8859-1", "ignore")

    def _pba_book_get_txt_lines(self, options):
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
            "|",
            ("tax_line_id.type_tax_use", "=", "sale"),
            ("tax_line_id.l10n_ar_withholding_payment_type", "=", "purchase"),
        ] + self._pba_book_get_lines_domain(options)
        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _pba_book_get_lines_domain(self, options):
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

    def _get_pba_txt_content(self, move_lines, type):
        """Returns the lines to be printed in the txt file."""
        lines = []
        # TODO implementar
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""

            lines.append(content)
        return lines
