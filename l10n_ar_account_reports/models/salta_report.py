# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError

from .helpers import get_standard_lines_domain, remove_accents_and_dieresis, validate_document_numbers

# Tipos de comprobante que acepta SIPOT en el F912 (pág. 18 de "Información General SIPOT").
SALTA_DOCUMENT_TYPES = {"invoice": "FA", "debit_note": "ND", "credit_note": "NC"}
SALTA_DOCUMENT_LETTERS = ("A", "B", "C")


class L10n_ArSaltaReportHandler(models.AbstractModel):
    _name = "l10n_ar.salta.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian Salta Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options["buttons"].append(
            {
                "name": "TXT Percepciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "salta_perc_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            }
        )

    def salta_perc_txt(self, options):
        return {
            "file_name": "F912 Percepciones Salta.txt",
            "file_content": self._salta_get_txt_files(options),
            "file_type": "txt",
        }

    def _salta_get_txt_files(self, options):
        """Returns Salta F912 txt content"""
        move_lines = self._salta_get_txt_lines(options)
        validate_document_numbers(move_lines)
        return "".join(self._get_salta_perc_txt_content(move_lines)).encode("ISO-8859-1", "ignore")

    def _salta_get_txt_lines(self, options):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "=", "A"),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
            ("tax_line_id.type_tax_use", "=", "sale"),
        ] + get_standard_lines_domain(self.env["account.report"].get_report_company_ids(options), options)
        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _salta_document_type(self, move):
        """Código SIPOT del comprobante (FA_A, NC_B, ...); OTRO si el tipo no está en la lista."""
        document_type = move.l10n_latam_document_type_id
        sipot_type = SALTA_DOCUMENT_TYPES.get(document_type.internal_type)
        if sipot_type and document_type.l10n_ar_letter in SALTA_DOCUMENT_LETTERS:
            return f"{sipot_type}_{document_type.l10n_ar_letter}"
        return "OTRO"

    def _get_salta_perc_txt_content(self, move_lines):
        """Registros del formulario F912 (SIPOT 3.3, "Información General SIPOT", pág. 18), 140 caracteres."""
        lines = []
        for line in move_lines:
            move = line.move_id
            parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number, line.l10n_latam_document_type_id.code
            )
            partner = line.partner_id

            content = ""
            # Fecha, ddmmaaaa (8)
            content += line.date.strftime("%d%m%Y")
            # Tipo de comprobante, código de la lista (4)
            content += self._salta_document_type(move).ljust(4)
            # Número de comprobante, ceros a la izquierda (20)
            content += (str(parts["point_of_sale"]).zfill(4) + str(parts["invoice_number"]).zfill(8)).zfill(20)
            # Nombre, blancos a la derecha (60). Latin-1 first: the final encode would drop chars and shift fields
            name = remove_accents_and_dieresis(partner.name or "").encode("ISO-8859-1", "ignore").decode("ISO-8859-1")
            content += name[:60].ljust(60)
            # CUIT sin guiones (11)
            content += partner.ensure_vat()
            # Monto, base de la percepción (16)
            content += "%016.2f" % abs(line.tax_base_amount)
            # Alícuota (5)
            content += "%05.2f" % line._get_settlement_tax().amount
            # Importe, con "-" a la izquierda en notas de crédito (16)
            content += "%016.2f" % -line.balance
            content += "\r\n"
            lines.append(content)
        return lines
